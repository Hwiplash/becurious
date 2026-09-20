from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_rag_index import embed_with_retry, prepare_records


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="특산물 청크를 기존 RAG 임베딩 인덱스에 증분 추가합니다.")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "processed" / "specialty_chunks.json")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data" / "rag_index")
    parser.add_argument("--model", default=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    chunk_path = args.index_dir / "chunks.json"
    vector_path = args.index_dir / "embeddings.npy"
    manifest_path = args.index_dir / "manifest.json"
    if not args.input.exists() or not chunk_path.exists() or not vector_path.exists():
        raise SystemExit("특산물 청크 또는 기존 RAG 인덱스가 없습니다.")

    current = json.loads(chunk_path.read_text(encoding="utf-8"))
    specialty_raw = json.loads(args.input.read_text(encoding="utf-8"))
    specialty, skipped = prepare_records(specialty_raw, min_chars=40)
    current_ids = {item["id"] for item in current}
    new_records = [item for item in specialty if item["id"] not in current_ids]
    print(json.dumps({
        "existing_chunks": len(current), "specialty_chunks": len(specialty),
        "new_chunks": len(new_records), "skipped": skipped,
    }, ensure_ascii=False, indent=2))
    if args.dry_run or not new_records:
        return
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 비어 있습니다.")

    client = OpenAI()
    vectors: list[list[float]] = []
    for start in range(0, len(new_records), args.batch_size):
        batch = new_records[start:start + args.batch_size]
        response = embed_with_retry(client, args.model, [item["embedding_text"] for item in batch])
        vectors.extend(item.embedding for item in response.data)
        print(f"embedded {min(start + args.batch_size, len(new_records))}/{len(new_records)}", flush=True)

    added = np.asarray(vectors, dtype=np.float32)
    added /= np.where(np.linalg.norm(added, axis=1, keepdims=True) == 0, 1, np.linalg.norm(added, axis=1, keepdims=True))
    existing = np.load(vector_path)
    if existing.shape[1] != added.shape[1]:
        raise SystemExit(f"임베딩 차원이 다릅니다: {existing.shape[1]} != {added.shape[1]}")
    for item in new_records:
        item.pop("embedding_text", None)
    combined_chunks = current + new_records
    combined_vectors = np.vstack([existing, added])
    chunk_path.write_text(json.dumps(combined_chunks, ensure_ascii=False), encoding="utf-8")
    np.save(vector_path, combined_vectors)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({
        "model": args.model,
        "prepared_records": len(combined_chunks),
        "specialty_records": sum(item.get("chunk_type") == "regional-specialty" for item in combined_chunks),
        "industry_taxonomy_records": sum(item.get("chunk_type") == "industry-taxonomy" for item in combined_chunks),
        "dimensions": int(combined_vectors.shape[1]),
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: 지식 청크 {len(new_records)}개 추가, 전체 {len(combined_chunks)}개")


if __name__ == "__main__":
    main()
