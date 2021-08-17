import logging

from copy import deepcopy
from enum import Enum, unique
from pathlib import Path
from typing import Union
from anytree import NodeMixin, PreOrderIter, RenderTree, LevelOrderGroupIter

from qaseio.client.models import (
    TestSuiteCreate,
    TestSuiteUpdate,
    TestCaseCreate,
    TestCaseUpdate,
)
from qaseio.client.services import BadRequestException

from . import config
from .api import get_all_suites, get_all_cases
from .string import strip_title


logger = logging.getLogger(__name__)


class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


@unique
class Location(Enum):
    LOCAL = 'local'
    REMOTE = 'remote'


@unique
class Entity(Enum):
    REPOSITORY = 'repository'
    # PARENT_S = 'suite'
    SUITE = 'suite'
    CASE = 'case'


@unique
class Action(Enum):
    NONE   = '-None-'
    CREATE = 'Create'
    UPDATE = 'Update'
    DELETE = 'Delete'

    @property
    def color(self):
        if self == Action.CREATE:
            return Color.OKGREEN
        elif self == Action.UPDATE:
            return Color.OKCYAN
        elif self == Action.DELETE:
            return Color.FAIL
        elif self == Action.NONE:
            return Color.BOLD
        return ''

    def render(self, string: str = '', ignore_none: bool = False) -> str:
        if self == Action.NONE and ignore_none:
            return ''

        color = self.color
        string = string or self.value
        if color:
            return f'{color}[{string}]{Color.ENDC}'
        return string


class LocalCaseNode(NodeMixin):
    def __init__(
        self,
        filepath: Union[str, Path] = '',
        name: str = '',
        entity: Entity = Entity.SUITE,
        action: Action = Action.NONE,
        data=None,
        parent=None,
        children=None,
    ):
        """Case node constructor

        Parameters
        ----------
        filepath
            Path to file case/suite location. For local files it refers to an actual
            file location. For remote objects it represents
        name
            Object name. Either taken from filepath stem or set explicitly
        entity
            Type of node
        data
            Additional data to include when sending over API. Contains data not represented
            in this instance's attributes (description, steps, etc.)
        parent
            Reference to parent node
        children
            References to children nodes
        """

        super().__init__()
        self.entity = entity
        self.filepath = Path(filepath)
        self.action = action

        if self.filepath == Path("."):
            self.entity = Entity.REPOSITORY
            self.name = "Repository"
        elif entity == Entity.SUITE:
            # stem will omit .feature extension
            self.name = self.filepath.stem
        elif entity == Entity.CASE:
            if not name:
                raise ValueError('Cannot create Test Case node without name')

            if config.STRIP_TITLES:
                self.name = strip_title(name, "'\"")
            else:
                self.name = name

        self.data = data or {}

        if parent:
            self.parent = parent
        if children:
            self.children = children

        self.custom_fields = []
        self.custom_field = {}
        self._set_key()

    def _set_key(self):
        base = str(self.filepath).replace('.feature', '')
        if self.entity == Entity.CASE:
            self.key = f'{base}::{self.name}'
        else:
            self.key = f'{base}'


class RemoteCaseNode(NodeMixin):
    def __init__(
        self,
        pk,
        entity: Entity = Entity.SUITE,
        action: Action = Action.NONE,
        name: str = '',
        parent_id=None,
        parent=None,
        children=None,
        custom_fields=None
    ):
        super().__init__()
        self.pk = pk
        self.entity = entity
        self.name = name
        self.parent_id = parent_id
        self.action = action

        if parent:
            self.parent = parent
        if children:
            self.children = children

        self.custom_fields = custom_fields

        self._set_remote_filepath()
        self._set_key()

    @property
    def custom_fields(self):
        return self._custom_fields

    @custom_fields.setter
    def custom_fields(self, x):
        '''Set _custom_fields and custom_field [sic, note plural/singular form]

        On retrieve action, Qase returns custom_fields [plural] as a list of
        {'id': id, 'value': value}, but when you post/update objects, it expects
        custom_field [singular] as a single {id: value} dict
        '''
        self._custom_fields = x

        # setting initial values to make sure Qase won't complain that some field is absent
        self.custom_field = deepcopy(config.QASE_CUSTOM_FIELD_DEFAULTS)

        # converting list of {'id': id, 'value': value} to single {id: value} dict
        x = x if x else []
        for dic in x:
            id_, value = dic['id'], dic['value']
            self.custom_field[id_] = value

    def _set_remote_filepath(self):
        """Creates fake filepath for remote objects.

        This is later used to initialize unique keys and to compare trees
        """

        if self.entity == Entity.REPOSITORY or self.parent is None:
            self.filepath = Path(".")
        elif self.parent and self.entity == Entity.SUITE:
            self.filepath = self.parent.filepath / self.name
        elif self.parent and self.entity == Entity.CASE:
            self.filepath = self.parent.filepath

    def _set_key(self):
        if self.entity == Entity.CASE:
            self.key = f'{str(self.filepath)}::{self.name}'
        else:
            self.key = f'{str(self.filepath)}'


class Tree:
    def __init__(self, root):
        self.root = root

        # maps remote node id to node reference (required to build remote tree)
        try:
            self.id_map = {root.pk: root}
        except AttributeError:
            self.id_map = {}

        # maps unique node key to node reference (required for local/remote tree comparison)
        self.key_map = {root.key: root}

    def get_node_by_suite_id(self, suite_id):
        return self.id_map.get(suite_id, None)

    def get_node_by_key(self, key):
        return self.key_map.get(key, None)

    def add_node(self, node):
        self.key_map[node.key] = node
        if getattr(node, 'pk', None):
            self.id_map[node.pk] = node

    def delete_node(self, node):
        self.key_map.pop(node.key)
        self.id_map.pop(node.pk)
        node.parent = None

    def add_local_suite(self, parent, filepath):
        node = LocalCaseNode(entity=Entity.SUITE, parent=parent, filepath=filepath)
        self.key_map[node.key] = node
        return node

    def add_local_case(self, parent, filepath, name):
        node = LocalCaseNode(entity=Entity.CASE, parent=parent, filepath=filepath, name=name)
        self.key_map[node.key] = node
        return node

    def add_remote_suite(self, suite):
        parent = self.id_map.get(suite.parent_id, None)
        node = RemoteCaseNode(
            suite.id,
            entity=Entity.SUITE,
            name=suite.title,
            parent=parent
        )
        self.id_map[suite.id] = node
        self.key_map[node.key] = node

    def add_remote_case(self, case):
        parent = self.id_map.get(case.suite_id, None)
        node = RemoteCaseNode(
            case.id,
            entity=Entity.CASE,
            name=case.title,
            parent=parent,
            custom_fields=case.custom_fields,
        )
        # id_map[case.id] = node
        self.key_map[node.key] = node

    def render(self, attrname='key', show_actions=False):
        render_case_tree(self.root, attrname=attrname, show_actions=show_actions)

    def delete_remotely(self):
        delete_tree_remotely(self.root)

    def truncate_to(self, root_suite_id):
        for node in self.root.children:
            if node.entity != Entity.SUITE:
                continue

            if node.pk != root_suite_id:
                self.id_map.pop(node.pk)
                self.key_map.pop(node.key)
                node.parent = None

    def create_all(self, root_suite_id=config.QASE_ROOT_SUITE_ID):
        '''Pushes everything regardless of Action. Not to be used in production!'''
        create_nodes(self.root, root_suite_id=root_suite_id)

    def push(self, root_suite_id=config.QASE_ROOT_SUITE_ID, dry_run=False):
        # For CREATE and UPDATE actions we traverse tree from top to bottom
        for node in PreOrderIter(self.root):
            if node.action == Action.NONE:
                continue
            elif node.action in [Action.CREATE, Action.UPDATE]:
                self.perform_action(node, root_suite_id, dry_run=dry_run)

        # for DELETE, we traverse tree from bottom (deepmost node) to top, thus
        # guaranteeing that parent will not be deleted prior to a child
        for level in reversed(group_nodes_by_level(self.root)):
            for node in level:
                if node.action in [Action.DELETE]:
                    self.perform_action(node, root_suite_id, dry_run=dry_run)

    def perform_action(self, node, root_suite_id, dry_run=False):
        try:
            pk = f'[{node.pk}] ' if getattr(node, 'pk', '') else ''
            msg = f"{node.action.render()} {node.entity.value} node {pk}{node.key}"
            if dry_run:
                print(msg)
                return
            else:
                logger.info(msg)

            if node.entity in [Entity.REPOSITORY, Entity.SUITE] and node.filepath == Path("."):
                # We assume it's impossible for Entity.CASE to be the root node
                node.pk = root_suite_id  # root node
            elif node.entity == Entity.SUITE:
                self.perform_action_on_suite(node, root_suite_id)
            elif node.entity == Entity.CASE:
                self.perform_action_on_case(node, root_suite_id)
        except BadRequestException as err:
            if 'There are no changes' in str(err):
                pass
            else:
                raise err

    def perform_action_on_suite(self, node, root_suite_id):
        if node.action == Action.CREATE:
            suite = config.qase.suites.create(
                config.QASE_PROJECT_CODE,
                TestSuiteCreate(node.name, parent_id=node.parent.pk)
            )
            node.pk = suite.id
            # self.add_remote_suite(suite)
        elif node.action == Action.UPDATE:
            suite = config.qase.suites.update(
                config.QASE_PROJECT_CODE,
                node.pk,
                TestSuiteUpdate(node.name, parent_id=node.parent.pk)
            )
            node.pk = suite.id
        elif node.action == Action.DELETE:
            suite = config.qase.suites.delete(config.QASE_PROJECT_CODE, node.pk)
            self.delete_node(node)

    def perform_action_on_case(self, node, root_case_id):
        if node.action == Action.CREATE:
            case = config.qase.cases.create(
                config.QASE_PROJECT_CODE,
                TestCaseCreate(title=node.name, suite_id=node.parent.pk,
                               custom_field=node.custom_field, **node.data)
            )
            node.pk = case.id
        elif node.action == Action.UPDATE:
            case = config.qase.cases.update(
                config.QASE_PROJECT_CODE,
                node.pk,
                TestCaseUpdate(title=node.name, suite_id=node.parent.pk,
                               custom_field=node.custom_field, **node.data)
            )
            node.pk = case.id
        elif node.action == Action.DELETE:
            case = config.qase.cases.delete(config.QASE_PROJECT_CODE, node.pk)
            self.delete_node(node)


def group_nodes_by_level(root):
    return [children for children in LevelOrderGroupIter(root)]


def render_case_tree(root_node, attrname='name', show_actions=False):
    for pre, fill, node in RenderTree(root_node):
        status = f'{node.action.render()} ' if show_actions and getattr(node, 'action', None) else ''
        pk = getattr(node, "pk", '')
        pkstr = f'[{pk}] ' if pk else ''
        print(f'{pre}{status}{pkstr}{getattr(node, attrname)}')


def delete_tree_remotely(root):
    for level in reversed(group_nodes_by_level(root)):
        for node in level:
            if node.pk == root.pk:
                # we don't want to delete root node
                continue

            if node.entity == Entity.CASE:
                config.qase.cases.delete(config.QASE_PROJECT_CODE, node.pk)
            elif node.entity == Entity.SUITE:
                config.qase.suites.delete(config.QASE_PROJECT_CODE, node.pk)


def create_nodes(root_node, root_suite_id=config.QASE_ROOT_SUITE_ID):
    for node in PreOrderIter(root_node):
        create_node(node, root_suite_id=root_suite_id)


def create_node(node, root_suite_id=config.QASE_ROOT_SUITE_ID):
    logger.info(f"Dumping node [{node.entity}] {node.name}")

    if node.entity == Entity.REPOSITORY or node.filepath == Path("."):
        # root node
        node.pk = root_suite_id
    elif node.entity == Entity.SUITE:
        suite = config.qase.suites.create(
            config.QASE_PROJECT_CODE,
            TestSuiteCreate(node.name, parent_id=node.parent.pk)
        )
        node.pk = suite.id
    elif node.entity == Entity.CASE:
        case = config.qase.cases.create(
            config.QASE_PROJECT_CODE,
            TestCaseCreate(node.name, suite_id=node.parent.pk, **node.data)
        )
        node.pk = case.id


def flat_diff_trees(local, remote):
    to_update = []
    to_create = []
    to_delete = []

    for key, node_local in local.key_map.items():
        if node_local.filepath == Path('.'):
            continue

        try:
            node_remote = remote.key_map[key]
            to_update.append((Action.UPDATE, node_local, node_remote.pk))
        except KeyError:
            to_create.append((Action.CREATE, node_local, None))

    for key, node_remote in remote.key_map.items():
        if node_remote.filepath == Path('.'):
            continue

        try:
            node_local = local.key_map[key]
            continue
        except KeyError:
            # key exists remotely but doesn't exist locally, meaning we deleted this node
            to_delete.append((Action.DELETE, node_remote, node_remote.pk))

    operations = to_update + to_create + to_delete
    return operations


def diff_trees(local, remote):
    '''Produces a merged tree that contains operation statuses'''
    merged = deepcopy(local)

    for key, node_merged in merged.key_map.items():
        try:
            node_remote = remote.key_map[key]
            node_merged.pk = node_remote.pk

            # Qase doesn't let us update test cases without specifying
            # value for each custom field, hence we retrieve them from remote tree
            node_merged.custom_fields = deepcopy(node_remote.custom_fields)
            node_merged.custom_field = deepcopy(node_remote.custom_field)

            if node_merged.filepath == Path('.'):
                node_merged.action = Action.NONE
            else:
                node_merged.action = Action.UPDATE
        except KeyError:
            node_merged.custom_field = deepcopy(config.QASE_CUSTOM_FIELD_DEFAULTS)
            node_merged.action = Action.CREATE

    for node_remote in PreOrderIter(remote.root):
        node_merged = merged.get_node_by_key(node_remote.key)
        if node_merged:  # node already exists, skipping
            continue

        # finding where to attach node we're copying from remote
        node_merged = deepcopy(node_remote)
        node_merged.children = []
        node_merged_parent = merged.get_node_by_key(node_remote.parent.key)
        node_merged.parent = node_merged_parent
        node_merged.action = Action.DELETE
        merged.add_node(node_merged)

    return merged


def merge_trees(local, remote):
    diff_trees(local, remote)  # sets actions for each tree
    merged = deepcopy(local)
    for node_remote in PreOrderIter(remote.root):
        node_merged = merged.get_node_by_key(node_remote.key)
        if node_merged:
            continue

        node_merged = deepcopy(node_remote)

        # finding where to attach node we're copying from remote
        node_remote_parent_key = node_remote.parent.key
        node_merged_parent = merged.get_node_by_key(node_remote_parent_key)
        node_merged.parent = node_merged_parent

    return merged


def render_operations(operations, attr='key'):
    for action, node, pk in operations:
        print(f'{action.color}[{action.value}]{Color.ENDC} {getattr(node, attr)}')
