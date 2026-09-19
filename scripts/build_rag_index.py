from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare_records(records: list[dict], min_chars: int) -> tuple[list[dict], dict]:
    prepared, seen = [], set()
    skipped = {"empty": 0, "short": 0, "duplicate": 0}
    for item in records:
        text = re.sub(r"\s+", " ", item.get("text", "")).strip()
        if not text:
            skipped["empty"] += 1
            continue
        if len(text) < min_chars:
            skipped["short"] += 1
            continue
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if digest in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(digest)
        record = {**item, "text": text}
        record["embedding_text"] = "\n".join(filter(None, [
            f"문서: {item.get('source', '')}",
            f"지역: {', '.join(item.get('regions', []))}",
            f"주제: {', '.join(item.get('topics', []))}",
            f"절: {item.get('section', '')}",
            f"본문: {text}",
        ]))
        prepared.append(record)
    return prepared, skipped


def embed_with_retry(client: OpenAI, model: str, inputs: list[str], attempts: int = 5):
    for attempt in range(attempts):
        try:
            return client.embeddings.create(model=model, input=inputs)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(min(2 ** attempt, 16))


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="로컬 PDF를 OpenAI 임베딩 기반 검색 인덱스로 변환합니다.")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "processed" / "chunks.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "rag_index")
    parser.add_argument("--model", default=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--min-chars", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"전처리 결과가 없습니다: {args.input}\n먼저 scripts/build_local_corpus.py를 실행하세요.")
    raw_records = json.loads(args.input.read_text(encoding="utf-8"))
    records, skipped = prepare_records(raw_records, args.min_chars)
    if not records:
        raise SystemExit(f"임베딩할 레코드가 없습니다: {args.input}")
    audit = {
        "model": args.model,
        "input": str(args.input),
        "raw_records": len(raw_records),
        "prepared_records": len(records),
        "skipped": skipped,
        "max_characters": max(len(item["embedding_text"]) for item in records),
    }
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if args.dry_run:
        return
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 비어 있습니다. .env에 키를 입력하세요.")
    if (args.output_dir / "embeddings.npy").exists() and not args.force:
        raise SystemExit("기존 인덱스가 있습니다. 다시 만들려면 --force를 사용하세요.")
    client = OpenAI()
    vectors: list[list[float]] = []
    for start in range(0, len(records), args.batch_size):
        batch = records[start:start + args.batch_size]
        inputs = [item["embedding_text"] for item in batch]
        response = embed_with_retry(client, args.model, inputs)
        vectors.extend(item.embedding for item in response.data)
        print(f"embedded {min(start + args.batch_size, len(records))}/{len(records)}", flush=True)

    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / np.where(norms == 0, 1, norms)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for item in records:
        item.pop("embedding_text", None)
    (args.output_dir / "chunks.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    np.save(args.output_dir / "embeddings.npy", matrix)
    (args.output_dir / "manifest.json").write_text(
        json.dumps({**audit, "dimensions": int(matrix.shape[1])}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"완료: {len(records)}개 청크 → {args.output_dir}")


if __name__ == "__main__":
    main()
