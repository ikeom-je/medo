from medo_core.nodes import Node, ScopedNode


def test_node_defaults_to_open_confidence_and_empty_id():
    node = Node(text="現状は手作業")

    assert node.id == ""
    assert node.confidence == "open"
    assert node.evidence_refs == []


def test_scoped_node_defaults_to_core_scope():
    node = ScopedNode(text="現状は手作業")

    assert node.scope == "core"
