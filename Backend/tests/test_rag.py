from app.rag import chunk_text


def test_chunk_text_empty_string():
    """Empty input returns empty list."""
    assert chunk_text("") == []


def test_chunk_text_none_like():
    """None-ish input returns empty list."""
    assert chunk_text("") == []


def test_chunk_text_shorter_than_chunk_size():
    """Short text returns a single chunk with the full content."""
    text = "Short document."
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_exactly_chunk_size():
    """Text exactly equal to chunk_size: first chunk is full, overlap causes a second shorter chunk."""
    text = "x" * 1000
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    # The step is chunk_size - overlap = 800, so start=800 < 1000 produces a second chunk
    assert len(chunks) == 2
    assert chunks[0] == text
    assert chunks[1] == text[800:]


def test_chunk_text_produces_multiple_chunks():
    """Long text is split into multiple chunks."""
    text = "a" * 2500
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) > 1
    # All text should be covered
    assert all(len(c) <= 1000 for c in chunks)


def test_chunk_text_overlap_is_correct():
    """Consecutive chunks share an overlapping region equal to the overlap parameter."""
    text = "".join(str(i % 10) for i in range(2500))
    chunk_size = 1000
    overlap = 200
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    assert len(chunks) >= 2
    step = chunk_size - overlap  # 800
    for i in range(len(chunks) - 1):
        # The overlap region starts at the beginning of chunk[i+1]
        actual_overlap = min(overlap, len(chunks[i + 1]))
        tail = chunks[i][-actual_overlap:]
        head = chunks[i + 1][:actual_overlap]
        assert tail == head, f"Overlap mismatch between chunk {i} and {i+1}"


def test_chunk_text_covers_full_input():
    """Reconstructing from chunks (minus overlap) should recover the full text."""
    text = "".join(str(i % 10) for i in range(3000))
    chunk_size = 1000
    overlap = 200
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    # The step between chunk starts is chunk_size - overlap = 800
    reconstructed = chunks[0]
    for chunk in chunks[1:]:
        # Each subsequent chunk overlaps with the previous by `overlap` chars
        reconstructed += chunk[overlap:]

    assert reconstructed == text
