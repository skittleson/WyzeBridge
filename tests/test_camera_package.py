import os
import sys
import unittest

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "home_assistant"))
import generate_camera_package as gen

CAMERAS = [
    {"mac": "AN_RSCW_80482CD21F56", "nickname": "Garden"},
    {"mac": "AN_RSCW_80482CD22376", "nickname": "Garden"},
    {"mac": "D03F279F990F", "nickname": "Gate Cam"},
]


class EnvVarLoader(yaml.SafeLoader):
    pass


EnvVarLoader.add_constructor("!env_var", lambda loader, node: ("ENV", loader.construct_scalar(node)))


class TestCameraPackage(unittest.TestCase):
    def setUp(self):
        self.package = yaml.load(gen.to_yaml(gen.build_package(CAMERAS)), Loader=EnvVarLoader)
        self.template = self.package["template"][0]

    def test_resource_comes_from_env_var(self):
        self.assertEqual(self.package["rest"][0]["resource"], ("ENV", "WYZE_CAMERAS_URL"))

    def test_duplicate_nicknames_get_mac_suffix(self):
        names = [e["name"] for e in self.template["binary_sensor"]]
        self.assertIn("Garden 1F56 Online", names)
        self.assertIn("Garden 2376 Online", names)
        self.assertIn("Gate Cam Online", names)

    def test_entities_per_camera(self):
        self.assertEqual(len(self.template["sensor"]), 2 * len(CAMERAS))
        self.assertEqual(len(self.template["binary_sensor"]), 2 * len(CAMERAS))

    def test_image_entity_per_camera(self):
        images = self.template["image"]
        self.assertEqual(len(images), len(CAMERAS))
        gate = next(e for e in images if e["name"] == "Gate Cam Last Event Image")
        self.assertIn("'D03F279F990F'", gate["url"])

    def test_unique_ids_are_unique(self):
        ids = [e["unique_id"] for kind in self.template.values() for e in kind]
        self.assertEqual(len(ids), len(set(ids)))

    def test_templates_reference_their_own_camera(self):
        online = next(e for e in self.template["binary_sensor"] if e["name"] == "Gate Cam Online")
        self.assertIn("'D03F279F990F'", online["state"])


if __name__ == "__main__":
    unittest.main()
