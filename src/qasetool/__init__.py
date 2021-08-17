__version__ = '0.9.1'

import argparse
import json
import logging
import os
import sys

from attr import attrs, attrib
from glob import iglob
from pathlib import Path

from qaseio.client import QaseApi
from qaseio.client.models import TestCaseCreate, TestSuiteCreate, TestCaseFilters

from . import config
from .api import get_all_suites, get_all_cases
from .gherkin import gherkin_as_nodes
from .tree import (
    LocalCaseNode,
    RemoteCaseNode,
    Tree,
    Entity,
    group_nodes_by_level,
    flat_diff_trees,
    diff_trees,
    merge_trees,
    render_operations,
)


logger = logging.getLogger(__name__)


def find_feature_files(target_dir):
    target_dir = Path(target_dir).expanduser()
    for filepath in target_dir.rglob("*.feature"):
        rel_filepath = filepath.relative_to(target_dir)
        yield rel_filepath, filepath


def parse_custom_fields_file(path):
    path = Path(path).expanduser()
    return json.load(open(path, 'r'))


def build_local_case_tree_branch(tree, rel_filepath, abs_filepath):
    dirs = [d for d in reversed(list(rel_filepath.parents)) if d != Path(".")]

    for prev, current in zip([None] + dirs, dirs + [rel_filepath]):
        node = tree.get_node_by_key(str(current))
        if not node:
            parent = tree.get_node_by_key(str(prev)) or tree.root
            node = tree.add_local_suite(parent, current)

            if current == rel_filepath:
                for case in gherkin_as_nodes(abs_filepath, node):
                    tree.add_node(case)
    return tree


def build_local_case_tree(target_dir):
    root_node = LocalCaseNode(entity=Entity.SUITE, filepath=".")
    tree = Tree(root_node)

    for rel_filepath, abs_filepath in find_feature_files(target_dir):
        build_local_case_tree_branch(tree, rel_filepath, abs_filepath)

    return tree


def build_remote_case_tree(root_suite_id=None):
    if root_suite_id:
        root_node = None
        tree = None
    else:
        root_node = RemoteCaseNode(None, entity=Entity.REPOSITORY, name="Repository")
        tree = Tree(root_node)

    suites = get_all_suites()
    for suite in suites:
        if root_suite_id:
            # omitting top-level suites that aren't our target
            if suite.parent_id is None and suite.id != root_suite_id:
                continue

            # omitting leaf suites whose parent is not present in our id_map,
            # i.e. from a branch we don't need
            if suite.parent_id is not None:
                if tree and not tree.get_node_by_suite_id(suite.parent_id):
                    continue
                if not tree:
                    continue

        if suite.id == root_suite_id and not root_node and not tree:
            root_node = RemoteCaseNode(
                suite.id,
                entity=Entity.SUITE,
                name=suite.title,
                parent_id=None,
                parent=None,
            )
            tree = Tree(root_node)
        else:
            tree.add_remote_suite(suite)

        cases = get_all_cases(filters=TestCaseFilters(suite_id=suite.id))
        for case in cases:
            tree.add_remote_case(case)

    # if root_suite_id:
    #     return tree.get_node_by_suite_id(root_suite_id)
    return tree


def push(args):
    tree_local = build_local_case_tree(args.path)
    tree_remote = build_remote_case_tree(args.root_suite_id)

    tree_merged = diff_trees(tree_local, tree_remote)
    tree_merged.push(
        root_suite_id=args.root_suite_id,
        dry_run=args.dry_run
    )


def render_flat_diff(args):
    tree_local = build_local_case_tree(args.path)
    tree_remote = build_remote_case_tree(args.root_suite_id)

    operations = flat_diff_trees(tree_local, tree_remote)
    render_operations(operations, args.attr)


def render_diff(args):
    tree_local = build_local_case_tree(args.path)
    tree_remote = build_remote_case_tree(args.root_suite_id)

    tree_merged = diff_trees(tree_local, tree_remote)
    tree_merged.render(attrname=args.attr, show_actions=True)


def render_local_tree(args):
    tree = build_local_case_tree(args.path)
    tree.render(args.attr)


def render_remote_tree(args):
    tree = build_remote_case_tree(root_suite_id=args.root_suite_id)
    tree.render(args.attr)


def delete_remote_tree(args):
    tree = build_remote_case_tree(root_suite_id=args.root_suite_id)
    tree.delete_remotely()


def dir_path(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid directory")


def file_path(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid file")


def main():
    parser = argparse.ArgumentParser(description='Parse .feature files and push to Qase')

    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )

    subparsers = parser.add_subparsers(title="subcommands", help='sub-command help')

    parser_path = argparse.ArgumentParser(add_help=False)
    parser_path.add_argument('path', metavar='path', type=dir_path,
                             help='Path to directory containing .feature files')

    parser_custom_fields_path = argparse.ArgumentParser(add_help=False)
    parser_custom_fields_path.add_argument(
        '-f', '--custom-fields-path', type=file_path,
        help='Path to .json file containing default custom fields mapping'
    )

    parser_attr = argparse.ArgumentParser(add_help=False)
    parser_attr.add_argument('-a', '--attr', metavar='<attr>', type=str,
                             default='name', help='Node attribute to render')

    parser_strip_titles = argparse.ArgumentParser(add_help=False)
    parser_strip_titles.add_argument('-s', '--strip-titles', action='store_true',
                                     help='Strip quotes and extra spaces from .feature titles')

    parser_exit_on_empty_files = argparse.ArgumentParser(add_help=False)
    parser_exit_on_empty_files.add_argument(
        '-e', '--exit-on-empty-files', action='store_true',
        help='Exit if it\'s impossible to parse .feature file (i.e. it\'s empty)'
    )

    parser_project_code = argparse.ArgumentParser(add_help=False)
    parser_project_code.add_argument(
        '-c', '--project-code', metavar='<code>', type=str,
        required=True,
        help='Code of a project where all auto-tests will be synced to'
    )

    parser_root_suite_id = argparse.ArgumentParser(add_help=False)
    parser_root_suite_id.add_argument(
        '-i', '--root-suite-id', metavar='<ID>', type=int,
        required=True,
        help='ID of a Qase suite where all auto-tests will be synced to'
    )

    parser_token = argparse.ArgumentParser(add_help=False)
    parser_token.add_argument(
        '-t', '--token', metavar='<token>', type=str,
        required=True,
        help='Qase API token'
    )

    parser_render_local = subparsers.add_parser(
        'render-local',
        parents=[parser_path, parser_attr, parser_strip_titles, parser_exit_on_empty_files]
    )
    parser_render_local.set_defaults(func=render_local_tree)

    parser_dry_run = argparse.ArgumentParser(add_help=False)
    parser_dry_run.add_argument(
        '--dry-run', dest='dry_run', action='store_true',
        help='Whether updates should be pushed to Qase or simply printed'
    )

    parser_push = subparsers.add_parser(
        'push',
        parents=[parser_path,
                 parser_token,
                 parser_root_suite_id,
                 parser_project_code,
                 parser_custom_fields_path,
                 parser_dry_run,
                 parser_strip_titles,
                 parser_exit_on_empty_files]
    )
    parser_push.set_defaults(func=push)

    parser_render_flat_diff = subparsers.add_parser(
        'render-flat-diff',
        parents=[parser_path,
                 parser_token,
                 parser_project_code,
                 parser_root_suite_id,
                 parser_attr,
                 parser_strip_titles,
                 parser_exit_on_empty_files]
    )
    parser_render_flat_diff.set_defaults(func=render_flat_diff)

    parser_render_diff = subparsers.add_parser(
        'render-diff',
        parents=[parser_path,
                 parser_token,
                 parser_project_code,
                 parser_root_suite_id,
                 parser_attr,
                 parser_strip_titles,
                 parser_exit_on_empty_files]
    )
    parser_render_diff.set_defaults(func=render_diff)

    parser_render_remote = subparsers.add_parser(
        'render-remote',
        parents=[parser_token,
                 parser_project_code,
                 parser_root_suite_id,
                 parser_attr]
    )
    parser_render_remote.set_defaults(func=render_remote_tree)

    parser_delete_remote = subparsers.add_parser(
        'delete-remote',
        parents=[parser_token,
                 parser_project_code,
                 parser_root_suite_id]
    )
    parser_delete_remote.set_defaults(func=delete_remote_tree)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    config.QASE_API_TOKEN = getattr(args, 'token', config.QASE_API_TOKEN)
    config.qase = QaseApi(config.QASE_API_TOKEN)

    config.QASE_PROJECT_CODE = getattr(args, 'project_code', config.QASE_ROOT_SUITE_ID)
    config.QASE_ROOT_SUITE_ID = getattr(args, 'root_suite_id', config.QASE_ROOT_SUITE_ID)

    if getattr(args, 'custom_fields_path', None):
        config.QASE_CUSTOM_FIELD_DEFAULTS = parse_custom_fields_file(args.custom_fields_path)

    config.STRIP_TITLES = getattr(args, 'strip_titles', config.STRIP_TITLES)

    exit_on_empty_files = getattr(args, 'exit_on_empty_files', False)
    config.SKIP_EMPTY_FILES = not exit_on_empty_files

    logging.basicConfig(level=args.loglevel)
    args.func(args)


if __name__ == '__main__':
    main()
