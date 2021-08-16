from qaseio.client import QaseApi
from . import config


def get_all_suites(limit=10, filters=None):
    offset = 0
    entities = []
    while True:
        response = config.qase.suites.get_all(config.QASE_PROJECT_CODE, offset=offset, limit=limit, filters=filters)
        if response.count == 0:
            break

        offset += limit
        entities.extend(response.entities)
    return entities


def get_all_cases(limit=10, filters=None):
    offset = 0
    entities = []
    while True:
        response = config.qase.cases.get_all(config.QASE_PROJECT_CODE, offset=offset, limit=limit, filters=filters)
        if response.count == 0:
            break

        offset += limit
        entities.extend(response.entities)
    return entities
