"""references/knowledge-graph.json: every edge lands on a node, every document node names a file that exists, the
evidence fields agree with the edges, and the numbers the READMEs quote are the graph's own.

Run:  python3 -m unittest discover -s tools/tests -v
"""

import collections
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.normpath(os.path.join(HERE, "..", ".."))
REFERENCES = os.path.join(LIBRARY, "references")
GRAPH = os.path.join(REFERENCES, "knowledge-graph.json")

# rel -> (type of `from`, type of `to`), as the graph's `about` declares them
SHAPE = {
    "explained_in": ("pattern", "kbDoc"),
    "documented_in": ("pattern", "libraryDoc"),
    "seen_in": ("pattern", "source"),
    "corrects": ("libraryGap", "kbDoc"),
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class KnowledgeGraphTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(read(GRAPH))
        cls.nodes = {n["id"]: n for n in cls.graph["nodes"]}
        cls.out = collections.defaultdict(list)
        for e in cls.graph["edges"]:
            cls.out[e["from"]].append((e["rel"], e["to"]))

    def of_type(self, kind):
        return [n for n in self.graph["nodes"] if n["type"] == kind]

    def test_ids_are_unique_and_every_edge_lands_on_a_node_of_the_declared_type(self):
        self.assertEqual(len(self.graph["nodes"]), len(self.nodes))
        triples = [(e["from"], e["rel"], e["to"]) for e in self.graph["edges"]]
        self.assertEqual(len(triples), len(set(triples)))
        for source, rel, target in triples:
            self.assertIn(rel, SHAPE)
            self.assertEqual(SHAPE[rel], (self.nodes[source]["type"], self.nodes[target]["type"]),
                             (source, rel, target))

    def test_every_document_node_is_a_file_that_exists(self):
        for kind, prefix, folder in (("kbDoc", "kb:", REFERENCES), ("libraryDoc", "lib:", LIBRARY)):
            for n in self.of_type(kind):
                self.assertEqual(prefix + n["path"], n["id"])
                self.assertTrue(os.path.isfile(os.path.join(folder, n["path"])), n["id"])

    def test_a_pattern_is_explained_once_documented_once_and_seen_where_it_says(self):
        for p in self.of_type("pattern"):
            rels = collections.defaultdict(list)
            for rel, target in self.out[p["id"]]:
                rels[rel].append(target)
            self.assertEqual(["kb:" + p["kbDoc"]], rels["explained_in"], p["id"])
            self.assertEqual(1, len(rels["documented_in"]), p["id"])
            self.assertEqual(sorted("src:" + s for s in p["seenIn"]), sorted(rels["seen_in"]), p["id"])
            if p["evidenceCount"] is None:
                self.assertEqual(([], "unrecorded"), (p["seenIn"], p.get("attribution")), p["id"])
            else:
                self.assertEqual(len(p["seenIn"]), p["evidenceCount"], p["id"])
                self.assertNotIn("attribution", p, p["id"])

    def test_a_gap_corrects_the_document_that_states_it(self):
        for gap in self.of_type("libraryGap"):
            self.assertEqual([("corrects", "kb:" + gap["kbDoc"])], self.out[gap["id"]], gap["id"])

    def test_the_numbers_the_readmes_quote_are_the_graphs_own(self):
        counts = self.graph["counts"]
        patterns = self.of_type("pattern")
        self.assertEqual((len(patterns), len(self.of_type("libraryGap")), len(self.graph["edges"])),
                         (counts["patterns"], counts["libraryGaps"], counts["edges"]))
        quoted = re.search(r"(\d+) nodes, (\d+) edges", read(os.path.join(LIBRARY, "README.md")))
        self.assertEqual((len(self.nodes), len(self.graph["edges"])), tuple(map(int, quoted.groups())))
        quoted = re.search(r"(\d+) of the (\d+) patterns carry `evidenceCount: null`",
                           read(os.path.join(REFERENCES, "README.md")))
        unrecorded = sum(1 for p in patterns if p["evidenceCount"] is None)
        self.assertEqual((unrecorded, len(patterns)), tuple(map(int, quoted.groups())))


if __name__ == "__main__":
    unittest.main()
