import sys
import argparse
from edit_version import EditVersionInXml


def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    # directory is manadatory
    required.add_argument(
        "--directory",
        help='''which directory to recursively find dashboards.
An example of $PATH_TO_VIEWS is
$SPLUNK_HOME/etc/apps/{app_name}/default/data/ui/views/''',
        type=str, required=True)
    # optional arguments
    optional.add_argument(
        "--skipVersions",
        help=("do not update dashboard version if the dashboard " +
              "version is among the specified version(s)"), type=str)
    optional.add_argument(
        "--version", help="the desired dashboard version", type=str)
    optional.add_argument(
        "--override",
        help="override existing dashboard version", type=bool)
    optional.add_argument(
        "--revert",
        help='''revert dashboards.
If revert is true, other optional arguments will be ignored.
After calling multiple updates only the original dashboards are backed up.''',
        type=bool)
    args = parser.parse_args()

    p = EditVersionInXml(
        args.directory, args.skipVersions, args.version, args.override)

    if args.revert:
        print("revert turned on")
        p.revert()
        return

    p.edit_xml_version()


if __name__ == "__main__":
    main(sys.argv[1:])
