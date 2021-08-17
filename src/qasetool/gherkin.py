import logging

from gherkin.parser import Parser
from tabulate import tabulate

from . import config
from .tree import Entity, LocalCaseNode


logger = logging.getLogger(__name__)


def parse_gherkin_document(path):
    parser = Parser()
    return parser.parse(str(path))


def iterate_scenarios(path, document):
    feature = document.get('feature', None)
    if not feature:
        msg = f'Couldn\'t parse file {str(path)}'
        if config.SKIP_EMPTY_FILES:
            logger.warning(msg)
            return
        else:
            raise ValueError(f'Couldn\'t parse file {str(path)}')

    background = None
    for child in feature.get('children', []):
        if 'background' in child.keys():
            background = child['background']
        if 'scenario' in child.keys():
            yield child['scenario'], background


def gherkin_as_nodes(path, parent):
    document = parse_gherkin_document(path)
    for scenario, background in iterate_scenarios(path, document):
        yield gherkin_scenario_as_node(scenario, background, path, parent)


def iterate_table_cells(source):
    for cell in source.get('cells', []):
        yield cell.get('value', '')


def gherkin_parse_scenario_fields(scenario):
    keyword = scenario.get('keyword')
    gh_description = scenario.get('description')
    steps = scenario.get('steps')
    examples = scenario.get('examples', [])

    description = f'**{keyword}**'
    if gh_description:
        description = f'{description}\n\n{gh_description}'

    if steps:
        description = f'{description}\n'
        for step in steps:
            keyword = step["keyword"].strip()  # parser returns leading space
            description = f'{description}\n**{keyword}** {step["text"]}'

    for example in examples:
        header_dict = example.get('tableHeader')
        header_row = [x for x in iterate_table_cells(header_dict)]

        body_list = example.get('tableBody')
        body_rows = []
        for body_dict in body_list:
            body_row = [x for x in iterate_table_cells(body_dict)]
            body_rows.append(body_row)

        table = tabulate(body_rows, header_row, tablefmt='github')
        description = f'{description}\n\n{table}'

    return dict(description=description)


def gherkin_parse_background_fields(background):
    '''Parses background

    Amusingly, background has the same fields that scenarios do
    '''
    if not background:
        return {}
    return gherkin_parse_scenario_fields(background)


def gherkin_scenario_as_node(scenario, background, path, parent):
    name = scenario.get('name')

    scenario_data = gherkin_parse_scenario_fields(scenario)
    scenario_desc = scenario_data.pop('description')

    background_data = gherkin_parse_background_fields(background)
    background_desc = background_data.pop('description', '')

    description = scenario_desc
    if background_desc:
        description = f'{background_desc}\n\n{scenario_desc}'

    background_data.update(scenario_data)
    data = background_data
    data['description'] = description

    return LocalCaseNode(
        name=name,
        filepath=parent.filepath,
        entity=Entity.CASE,
        data=data,
        parent=parent,
    )
