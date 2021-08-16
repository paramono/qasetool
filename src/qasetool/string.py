from typing import Tuple


def is_balanced(string: str, symbol: str) -> bool:
    return string.count(symbol) % 2 == 0


def _get_var_boundary_positions(string: str, symbol: str) -> Tuple[int, int]:
    var_start = string.find(f'{symbol}<')
    var_end = string.rfind(f'>{symbol}')
    if var_end != -1:
        # compensating for search pattern length: instead of position of '>'
        # we want to get position of {symbol}
        var_end += 1
    return var_start, var_end


def _handle_variables(string: str, symbol: str, balanced: bool = True) -> str:
    start = 0
    end = len(string) - 1
    symbol_start = string.find(symbol)
    symbol_end = string.rfind(symbol)
    var_start, var_end = _get_var_boundary_positions(string, symbol)

    if var_start == symbol_start and var_end == symbol_end:
        return string
    elif var_start == symbol_start == start and string[end] == symbol:
        return string[:end]
    elif var_end == symbol_end == end and string[start] == symbol:
        return string[start+1:]

    if balanced and string[start] == string[end] == symbol:
        return string[start+1:end]

    return string


def _strip_title(string: str, symbol: str) -> str:
    start = 0
    end = len(string) - 1

    if not (string[start] == symbol or string[end] == symbol):
        return string

    balanced = is_balanced(string, symbol)
    string = _handle_variables(string, symbol, balanced)

    # variable handling might have fixed balance, hence recalculating
    end = len(string) - 1
    balanced = is_balanced(string, symbol)
    if not balanced and string.count(symbol) == 1:
        # trailing symbol at the end or at the beginning
        if string[start] == symbol:
            string = string[start+1:]
        elif string[end] == symbol:
            string = string[:end]
    elif not balanced and string.count(symbol) == 3:
        # preserving quotes with the shortest distance and omitting the farthest one
        left_distance = string.find(symbol, start+1) - start
        right_distance = end - string.rfind(symbol, start, end)
        if left_distance > right_distance:
            string = string[start+1:]
        else:
            string = string[:end]
    elif not balanced and string.count(symbol) > 3:
        # we might have apostrophes and all sorts of other quotes we won't be able to handle
        # without NLP, hence trying to strip naively:
        var_start, var_end = _get_var_boundary_positions(string, symbol)
        if var_start != start and var_end != end and string[start] == string[end] == symbol:
            string = string[start+1:end]
    return string.strip(' ')


def strip_title(string: str, symbols: str) -> str:
    """Properly strip spaces and quotes from gherking title, plus omit multiple
    consecutive spaces

    Rationale: gherkin scenario name might contain variables wrapped in quotes,
    and default strip() implementation might remove quote from a '<variable>' if it
    is located at the string border
    """
    for symbol in symbols:
        string = _strip_title(string, symbol)
    return " ".join(string.split())  # convert multiple whitespace into a single one
