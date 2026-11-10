"""Carrega documentos Markdown e divide em chunks por seção (## Título)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str  # nome do arquivo, ex.: "cardapio.md"
    document: str  # título do documento (# ...)
    section: str  # título da seção (## ...)
    text: str

    @property
    def ref(self) -> str:
        return f"{self.source} › {self.section}"


def split_markdown(source: str, content: str) -> list[Chunk]:
    document = source
    chunks: list[Chunk] = []
    section: str | None = None
    lines: list[str] = []

    def flush() -> None:
        # Junta linhas quebradas do mesmo parágrafo, preservando itens de lista ("- ").
        body = re.sub(r"(?<!\n)\n(?!- |\n)", " ", "\n".join(lines).strip())
        if section and body:
            chunks.append(
                Chunk(
                    id=f"{source}#{len(chunks)}",
                    source=source,
                    document=document,
                    section=section,
                    text=body,
                )
            )

    for line in content.splitlines():
        if line.startswith("# "):
            document = line[2:].strip()
        elif line.startswith("## "):
            flush()
            section, lines = line[3:].strip(), []
        else:
            lines.append(line)
    flush()
    return chunks


def load_knowledge_base(directory: Path) -> list[Chunk]:
    files = sorted(directory.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"Nenhum documento .md encontrado em {directory}")
    chunks: list[Chunk] = []
    for path in files:
        chunks.extend(split_markdown(path.name, path.read_text(encoding="utf-8")))
    return chunks
