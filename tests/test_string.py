import pytest
from qasetool.string import strip_title


@pytest.mark.parametrize(
    'inp,expected', [
        ('Add New Team',
         'Add New Team'),
        ('Filter "Status-Active"',
         'Filter "Status-Active"'),
        ("'Search non-existent team'",
         "Search non-existent team"),
        ('"Member Directory Information"',
         'Member Directory Information'),
        ("'Remove '<fieldName>' field from display via Fields to Display control'",
         "Remove '<fieldName>' field from display via Fields to Display control"),
        ("'Add record via record modal with '<fieldName>' field'",
         "Add record via record modal with '<fieldName>' field"),
        ("Add '<fieldType>' field content in cell and press 'Enter' key",
         "Add '<fieldType>' field content in cell and press 'Enter' key"),
        ("'Edit record with '<fieldType>' field via Inline edit'",
         "Edit record with '<fieldType>' field via Inline edit"),
        ("'Add field '<fieldType>' with default settings from '+' column button in Grid view'",
         "Add field '<fieldType>' with default settings from '+' column button in Grid view"),
        ("'Select '<fieldType>' field to display via Fields to Display control'",
         "Select '<fieldType>' field to display via Fields to Display control"),
        ("'<fieldType>' field convert to '<convertedFieldType>'",
         "'<fieldType>' field convert to '<convertedFieldType>'"),
        ("'<fieldType>' field convert to '<convertedFieldType>': check empty value",
         "'<fieldType>' field convert to '<convertedFieldType>': check empty value"),
        ("'Сheck filter button in Grid'",
         "Сheck filter button in Grid"),
        ("' Multiple sort: delete sort control'",
         "Multiple sort: delete sort control"),
        ("'Exit without Saving?' confirmation popup for the \"Text\" field - "
         "Exit without changing'",
         "'Exit without Saving?' confirmation popup for the \"Text\" field - "
         "Exit without changing"),
        ("'Exit without Saving? confirmation popup for the \"Text\" field - "
         "'Exit without changing'",
         "Exit without Saving? confirmation popup for the \"Text\" field - "
         "'Exit without changing'"),
        ("'<fieldType>' field convert to '<convertedFieldType>': check existing value "
         "(+settings)'",
         "'<fieldType>' field convert to '<convertedFieldType>': check existing value "
         "(+settings)"),
        ("'<fieldType>' field Defaults option enabled: check existing empty value in Edit "
         "record window'",
         "'<fieldType>' field Defaults option enabled: check existing empty value in Edit "
         "record window"),
        ("'Card size:  check using 'plus' / 'minus' buttons in Card size toolbar in Kanban'",
         "Card size: check using 'plus' / 'minus' buttons in Card size toolbar in Kanban"),
        ("Edit field '<fieldName>' name to '<editedFieldName>'",
         "Edit field '<fieldName>' name to '<editedFieldName>'"),
        ("'Edit field '<fieldName>' name to '<editedFieldName>'",
         "Edit field '<fieldName>' name to '<editedFieldName>'"),
        ("'Validate deletion of '<fieldType>' field when it's applied in View "
         "controls - Sort by'",
         "Validate deletion of '<fieldType>' field when it's applied in View "
         "controls - Sort by"),
        ("\"Text\" field Require entries to be unique option enabled: add unique value "
         "in Edit record window'",
         "\"Text\" field Require entries to be unique option enabled: add unique value "
         "in Edit record window"),
        ("'<fieldType>' field Defaults option enabled : remove with 'Delete' key existing default value in Grid and disable Field Defaults option'",
         "'<fieldType>' field Defaults option enabled : remove with 'Delete' key existing default value in Grid and disable Field Defaults option"),
        ("'<fieldType>' field Defaults option enabled : remove with 'Delete' key existing default value in Grid and disable Field Defaults option",
         "'<fieldType>' field Defaults option enabled : remove with 'Delete' key existing default value in Grid and disable Field Defaults option")
    ]
)
def test_strip_title(inp, expected):
    string = inp
    string = strip_title(string, "'\"")
    assert string == expected
