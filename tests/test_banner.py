import unittest

import main
from utils import banner


class BannerIntegrityTests(unittest.TestCase):
    def test_main_banner_file_hash_matches_current_banner_file(self):
        self.assertTrue(main.banner_file_is_valid())

    def test_decrypt_banner_title_and_lines(self):
        self.assertEqual(banner.get_banner_title(), "Zhong")
        self.assertEqual(
            banner.get_banner_lines(),
            [
                "\u95f2\u9c7c\uff1a\u949f\u5c11\u5927\u738b666",
                "Github\uff1ahttps://github.com/netz888",
            ],
        )

    def test_banner_identity_hash_matches_expected_value(self):
        self.assertEqual(
            banner.compute_banner_identity_hash(
                banner.get_banner_title(),
                banner.get_banner_lines(),
            ),
            banner.EXPECTED_BANNER_IDENTITY_HASH,
        )

    def test_banner_identity_check_fails_for_modified_banner_lines(self):
        self.assertFalse(
            banner.banner_identity_is_valid(
                title=banner.get_banner_title(),
                lines=[banner.get_banner_lines()[0] + "x", *banner.get_banner_lines()[1:]],
            )
        )

    def test_banner_stop_message_is_chinese(self):
        self.assertEqual(
            banner.STOP_MESSAGE,
            "[-] Banner\u4fe1\u606f\u4e0d\u5141\u8bb8\u4fee\u6539\uff0c\u5df2\u505c\u6b62\u8fd0\u884c",
        )


if __name__ == "__main__":
    unittest.main()
