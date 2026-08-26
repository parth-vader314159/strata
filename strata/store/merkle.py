"""
strata.store.merkle
===================
Merkle trees over record digests.

WHY A TREE AND NOT A CHAIN

A hash chain (`h(n) = H(h(n-1) || record(n))`) proves the whole archive is
unaltered, which is useful. But it can only ever prove that: to convince
somebody that *one specific log line* is in the archive, you must hand them
every other record so they can recompute the chain. In a forensic or legal
setting that is often exactly what you cannot do -- the other records belong to
other cases, other customers, other people.

A Merkle tree gives an **inclusion proof**: about log2(n) sibling hashes that
let anyone recompute the root from a single record. For a stratum of a million
records that is 20 hashes -- a few hundred bytes. The verifier learns that this
line is in the archive and learns *nothing whatsoever* about any other line.

That is the difference between "trust our database" and evidence.

DOMAIN SEPARATION (RFC 6962)

Leaves are hashed with a 0x00 prefix and internal nodes with 0x01. Without
this, an attacker can present an internal node as if it were a leaf and forge
a proof for data that was never stored -- a second-preimage attack that has
bitten real systems. One byte, and the attack is impossible.

ODD NODES

When a level has an odd number of nodes the last is PROMOTED unchanged to the
next level, rather than duplicated. Duplicating the last node (as Bitcoin does)
makes two distinct trees produce the same root, which is its own vulnerability.
"""

from __future__ import annotations

import hashlib

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"

# Root of an empty stratum. Distinct from any real root because no leaf hashes
# to it -- every leaf hash includes the 0x00 prefix and at least one byte.
EMPTY_ROOT = b"\x00" * 32


def leaf_hash(record_id: bytes) -> bytes:
    """Hash a record digest into a Merkle leaf."""
    return hashlib.sha256(LEAF_PREFIX + record_id).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    """Hash two children into an internal node."""
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def build(record_ids: list[bytes]) -> list[list[bytes]]:
    """Build the full tree. Returns levels, leaves first, root last.

    Kept as levels (rather than just the root) because the proof generator
    needs them, and a stratum is sealed once so the cost is paid once.
    """
    if not record_ids:
        return [[]]

    levels: list[list[bytes]] = [[leaf_hash(r) for r in record_ids]]
    while len(levels[-1]) > 1:
        current = levels[-1]
        nxt: list[bytes] = []
        for i in range(0, len(current) - 1, 2):
            nxt.append(node_hash(current[i], current[i + 1]))
        if len(current) % 2:
            nxt.append(current[-1])          # promote, never duplicate
        levels.append(nxt)
    return levels


def root_of(record_ids: list[bytes]) -> bytes:
    """The Merkle root for a list of record digests."""
    if not record_ids:
        return EMPTY_ROOT
    return build(record_ids)[-1][0]


def proof(record_ids: list[bytes], index: int) -> list[tuple[str, bytes]]:
    """Inclusion proof for the record at `index`.

    Returns sibling hashes bottom-up as (side, hash), where side says whether
    the sibling sits on the "L" or "R" of the node being folded. A promoted
    node has no sibling at that level and contributes nothing.
    """
    if not 0 <= index < len(record_ids):
        raise IndexError(f"index {index} outside stratum of {len(record_ids)} records")

    levels = build(record_ids)
    path: list[tuple[str, bytes]] = []
    idx = index

    for level in levels[:-1]:
        if idx % 2 == 0:
            sibling = idx + 1
            if sibling < len(level):
                path.append(("R", level[sibling]))
            # else: this node was promoted; nothing to fold at this level
        else:
            path.append(("L", level[idx - 1]))
        idx //= 2
    return path


def verify(record_id: bytes, path: list[tuple[str, bytes]], expected_root: bytes) -> bool:
    """Recompute the root from one record and its proof.

    This is the function a third party runs. It needs the record, the proof,
    and the published root -- nothing else, and no access to the archive.
    """
    node = leaf_hash(record_id)
    for side, sibling in path:
        if side == "R":
            node = node_hash(node, sibling)
        elif side == "L":
            node = node_hash(sibling, node)
        else:
            return False
    return node == expected_root


def encode_proof(path: list[tuple[str, bytes]]) -> list[str]:
    """Proof in a form safe to put in JSON or hand to somebody on paper."""
    return [f"{side}:{h.hex()}" for side, h in path]


def decode_proof(encoded: list[str]) -> list[tuple[str, bytes]]:
    """Inverse of `encode_proof`. Rejects anything malformed rather than
    guessing -- a corrupted proof must fail loudly, not silently verify."""
    out: list[tuple[str, bytes]] = []
    for item in encoded:
        side, _, hexdigest = item.partition(":")
        if side not in ("L", "R") or len(hexdigest) != 64:
            raise ValueError(f"malformed proof element: {item!r}")
        out.append((side, bytes.fromhex(hexdigest)))
    return out
