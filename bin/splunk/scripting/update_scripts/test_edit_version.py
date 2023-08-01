import unittest
import os
from edit_version import EditVersionInXml
import shutil
import fnmatch
try:
    from unittest.mock import MagicMock
except ImportError:
    from mock import MagicMock


class TestClass(unittest.TestCase):
    def cleanup(self):
        if (os.path.exists(self.temp_path)):
            shutil.rmtree(self.temp_path)

    def setUp(self):
        dirname = os.path.dirname(__file__)
        self.path = os.path.join(dirname, './test_files')
        self.temp_path = os.path.join(dirname, './temp')
        self.version = '1.1'
        self.backup_extension = '.orig.xml'
        self.cleanup()
        shutil.copytree(self.path, self.temp_path)
        self.class_under_test = EditVersionInXml(self.temp_path)

    def tearDown(self):
        self.cleanup()

    def test_default_values(self):
        _instance = self.class_under_test
        self.assertEqual(_instance.version, self.version)
        self.assertEqual(_instance.directory, self.temp_path)
        self.assertEqual(_instance.skip_versions, ['2.0'])
        self.assertEqual(_instance.override, False)
        self.assertEqual(_instance.backup_extension, self.backup_extension)

    def test_find_dashboard_files(self):
        _instance = self.class_under_test
        file_list = _instance.find_dashboard_files()
        self.assertTrue(len(file_list) == 3)

    def test_find_dashboard_files_exclude_backup_files(
            self):
        _instance = self.class_under_test
        xml_file_list = self.get_files('.xml')
        self.assertTrue(len(xml_file_list) > 1)
        shutil.copyfile(
            xml_file_list[0],
            xml_file_list[0] + self.backup_extension)
        file_list = _instance.find_dashboard_files()
        self.assertTrue(len(file_list) > 1)

    def get_files(self, pattern):
        return [os.path.join(dirpath, f)
                for dirpath, dirnames, files in os.walk(self.temp_path)
                for f in fnmatch.filter(files, '*' + pattern)]

    def test_copy_file_if_no_backup_exists(self):
        xml_file_list = self.get_files('.xml')
        self.assertTrue(len(xml_file_list) > 1)
        none_list = self.get_files(self.backup_extension)
        self.assertEqual(len(none_list), 0)
        EditVersionInXml.copy_file_if_no_backup_exists(
            xml_file_list[0], '.xml', self.backup_extension)
        file_list = self.get_files(self.backup_extension)
        self.assertEqual(len(file_list), 1)

    @staticmethod
    def get_file_content(path):
        with open(path, 'r') as file:
            return file.read().replace('\n', '')

    def test_copy_file_does_not_change_copied_file(self):
        '''
        given file x
        make a copy of it
        change file x
        call copy
        assert the copy of file x has not changed
        '''
        xml_file_list = self.get_files(".xml")
        self.assertTrue(len(xml_file_list) > 1)
        new_path = xml_file_list[0].replace('.xml', self.backup_extension)
        shutil.copyfile(xml_file_list[0], new_path)
        data = self.get_file_content(new_path)

        f = open(xml_file_list[0], "w")
        f.write("Changed content")
        f.close()
        self.class_under_test.copy_file_if_no_backup_exists(
            xml_file_list[0], '.xml', self.backup_extension)
        self.assertEqual(data, self.get_file_content(new_path))

    def test_edit_version_calls_methods(self):
        xml_file_list = self.get_files(".xml")
        _class = self.class_under_test
        _class.find_dashboard_files = MagicMock(
            return_value=xml_file_list)
        _class.copy_file_if_no_backup_exists = MagicMock()
        _class.set_version = MagicMock()
        _class.edit_xml_version()
        self.assertTrue(
            _class.find_dashboard_files.assert_called)
        self.assertTrue(_class.copy_file_if_no_backup_exists.assert_called)
        self.assertTrue(_class.set_version.assert_called)

    def test_set_version_calls_method(self):
        xml_file_list = self.get_files(".xml")
        self.assertTrue(len(xml_file_list) > 1)
        self.class_under_test.set_version_in_tree = MagicMock()
        self.class_under_test.set_version(xml_file_list[0])
        self.assertTrue(
            self.class_under_test.set_version_in_tree.assert_called)

    def test_set_version_in_tree_returns_version(self):
        xml_file_list = self.get_files(".xml")
        self.assertTrue(len(xml_file_list) > 1)
        res = EditVersionInXml.set_version_in_tree(
            self.version, xml_file_list[0])
        self.assertEqual(res, self.version)

    def test_revert_calls_methods(self):
        # setup backup files
        xml_file_list = self.get_files(".xml")
        self.assertTrue(len(xml_file_list) > 1)
        for xml_path in xml_file_list:
            file_without_path = os.path.splitext(xml_path)[0]
            shutil.copyfile(
                xml_path, file_without_path + self.backup_extension)
        self.assertEqual(
            len(self.get_files(self.backup_extension)),
            len(xml_file_list))

        _instance = self.class_under_test
        mock_delete = _instance.delete_file = MagicMock()
        mock_rename = _instance.rename_file_with_extension = MagicMock()
        _instance.revert()
        self.assertEqual(mock_delete.call_count, len(xml_file_list))
        self.assertEqual(mock_rename.call_count, len(xml_file_list))

    def test_revert_does_not_call_methods(self):
        # given no backup files, delete and rename is not called
        _instance = self.class_under_test
        mock_delete = _instance.delete_file = MagicMock()
        mock_rename = _instance.rename_file_with_extension = MagicMock()
        _instance.revert()
        self.assertFalse(mock_delete.called)
        self.assertFalse(mock_rename.called)

    def test_delete_file(self):
        xml_file_list = self.get_files(".xml")
        original_len = len(xml_file_list)
        self.class_under_test.delete_file(xml_file_list[0])
        self.assertEqual(len(self.get_files(".xml")), original_len-1)

    def test_rename_file_with_extension(self):
        xml_file_list = self.get_files(".xml")
        self.assertTrue(len(xml_file_list) > 1)
        res = self.class_under_test.rename_file_with_extension(
            xml_file_list[0], '.xml', self.backup_extension)
        self.assertEqual(res.endswith(self.backup_extension), True)
        self.assertTrue(os.path.exists(res))

    def test_set_version_with_skip_version_does_not_set(self):
        # version should NOT be set due to skip_versions
        instance = EditVersionInXml(
            self.temp_path, skip_versions='1.1',
            version='2.0', override=True)
        instance.set_version_in_tree = MagicMock()
        instance.set_version(self.temp_path + '/version_1.1.xml')
        self.assertFalse(instance.set_version_in_tree.called)

    def test_set_version_with_skip_version_set(self):
        # version should NOT be set due to skip_versions
        instance = EditVersionInXml(
            self.temp_path, skip_versions='1.1,2.0',
            version='2.0', override=True)
        instance.set_version_in_tree = MagicMock()
        instance.set_version(self.temp_path + '/version_1.1.xml')
        self.assertFalse(instance.set_version_in_tree.called)

    def test_set_version_with_override(self):
        # override is true and version is not skipped
        instance = EditVersionInXml(
            self.temp_path, skip_versions='1.0',
            version='2.0', override=True)
        instance.set_version_in_tree = MagicMock()
        instance.set_version(self.temp_path + '/version_1.1.xml')
        self.assertTrue(instance.set_version_in_tree.called)

    def test_set_version_with_override_false(self):
        # override is false, do NOT set
        instance = EditVersionInXml(
            self.temp_path, skip_versions='1.0', version='2.0')
        instance.set_version_in_tree = MagicMock()
        instance.set_version(self.temp_path + '/version_1.1.xml')
        self.assertFalse(instance.set_version_in_tree.called)


if __name__ == "__main__":
    unittest.main()
