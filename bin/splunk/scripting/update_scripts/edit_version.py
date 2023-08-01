import os
import xml.etree.ElementTree as ET
import shutil
import fnmatch


class EditVersionInXml():
    '''Methods to set or revert the version attribute in a XML dashboard'''

    def __init__(
            self, directory,
            skip_versions='2.0', version='1.1', override=False):
        self.version = version if version is not None else '1.1'
        self.directory = directory
        self.skip_versions = skip_versions.split(',') if isinstance(
            skip_versions, str) else ['2.0']
        self.override = override
        self.backup_extension = '.orig.xml'

    def find_dashboard_files(self):
        '''
        Given a file extension recursively look for files in directory.
        Excludes backup files.
        '''
        file_list = [os.path.join(dirpath, f)
                     for dirpath, dirnames, files in os.walk(self.directory)
                     for f in fnmatch.filter(files, '*.xml')]
        dashboard_files = []
        for xml_file in file_list:
            # skip backup files
            if (xml_file.endswith(self.backup_extension)):
                continue
            tree = ET.parse(xml_file)
            root = tree.getroot()
            if root.tag == 'dashboard' or root.tag == 'form':
                dashboard_files.append(xml_file)
        return dashboard_files

    @staticmethod
    def copy_file_if_no_backup_exists(file_path, old_extension, new_extension):
        '''
        Check whether a file already exists with the new extension.
        If not, copy a file with the new extension.
        '''
        new_path = file_path.replace(old_extension, new_extension)
        if (os.path.exists(new_path) is False):
            shutil.copyfile(file_path, new_path)
            return new_path
        return

    def edit_xml_version(self):
        '''
        Filter through xml files to find the dashboards and
        potentially back them up, and/or set their version
        '''
        file_list = self.find_dashboard_files()
        print('Found', len(file_list), 'files in', self.directory)
        # filter dashboards
        print('Found', len(file_list), 'dashboards in', self.directory)
        for xml_file in file_list:
            self.copy_file_if_no_backup_exists(
                xml_file, '.xml', self.backup_extension)
            self.set_version(xml_file)

    def set_version(self, xml_file):
        '''
        Given a dashboard file path:
        1. if the dashboard does not have a version, set its version
        2. else if the dashboard has a version and the dashboard version:
            a. is not in the skip_versions: set the version
            a. is in the skip_versions: do not change the version
        3. print what was done, either no change or set the version
        '''
        tree = ET.parse(xml_file)
        root = tree.getroot()
        try:
            # will err if version attribute is missing
            _version = root.attrib['version']
            if _version not in self.skip_versions and self.override is True:
                print('version attribute', _version, 'found in file',
                      xml_file, 'setting version', self.version)
                self.set_version_in_tree(self.version, xml_file)
            else:
                print('Did not change version attribute for file', xml_file)
            return _version
        except (KeyError):
            print('no version attribute found in file',
                  xml_file, 'setting version', self.version)
            self.set_version_in_tree(self.version, xml_file)
            return

    @staticmethod
    def set_version_in_tree(version, xml_file):
        '''Given a dashboard file path, set the version attribute'''
        tree = ET.parse(xml_file)
        tree.getroot().set('version', version)
        tree.write(xml_file)
        return version

    def revert(self):
        '''
        Find all dashboard files and revert them to their backup file.
        Revert is aborted if there's a missing backup file
        '''
        file_list = self.find_dashboard_files()
        for xml_file in file_list:
            file_without_path = os.path.splitext(xml_file)[0]
            if (
                os.path.exists(
                    file_without_path + self.backup_extension) is False):
                print('missing backup file for', xml_file, 'stopping revert')
                break
            self.delete_file(xml_file)
            self.rename_file_with_extension(
                xml_file, self.backup_extension, '.xml')

    @staticmethod
    def delete_file(file_path):
        '''Delete a file'''
        os.remove(file_path)

    @staticmethod
    def rename_file_with_extension(
            file_with_path, old_extension, new_extension):
        '''Rename a file with the old extension to the new extension'''
        file_without_path = os.path.splitext(file_with_path)[0]
        old_path = file_without_path + old_extension
        new_path = file_without_path + new_extension
        print('rename', old_path, new_path)
        os.rename(old_path, new_path)
        return new_path
