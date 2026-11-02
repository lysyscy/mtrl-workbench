"""Read-only mechanical page projections and shared company-summary values.

The Excel renderer consumes company_rows too; page reads never build a workbook.
"""
from __future__ import annotations

def source_row(row):
    """Fields used to inspect an i8 document; raw source responses stay server-side."""
    return {field: row[field] for field in ('id', 'bill', 'periodName', 'periodKey', 'amount',
                                          'approval', 'projectId', 'status', 'workflow') if field in row}


def source_payload(payload):
    """Project before copying so discarded raw document sources are never cloned."""
    result = {field: value for field, value in payload.items() if field not in ('source', 'sources', 'unknown_documents')}
    if 'sources' in payload:
        result['sources'] = {kind: [source_row(row) for row in rows] for kind, rows in payload['sources'].items()}
    if 'unknown_documents' in payload:
        result['unknown_documents'] = [{**source_row(row), **({'kind': row['kind']} if 'kind' in row else {})}
                                       for row in payload['unknown_documents']]
    return result


def company_rows(data):
    """The original Excel company sheet's fifteen initial values, as strings/nulls.

    Weekly amounts and notes are applied by the page's existing presentation logic;
    Excel's later cross-sheet formulas still replace only matching known amounts.
    """
    ym = data['ym']
    summaries = {row['warehouse']: row for row in data.get('summary', []) if row['ym'] == ym}
    amounts = {row['warehouse']: row['values'] for row in data.get('annual_effective', data['effective']) if row['ym'] == ym}
    result = []
    for index, project in enumerate(data['projects'], 1):
        wh = project['warehouse']
        metadata = summaries.get(wh, {})
        cumulative = metadata.get('cumulative', {})
        monthly = amounts.get(wh, {})
        values = [index, project['name'], metadata.get('start_year'), metadata.get('start_month'),
                  cumulative.get('zero'), cumulative.get('monthly'), None,
                  cumulative.get('internal'), cumulative.get('company'),
                  monthly.get('mech_2'), monthly.get('mech_3'), None,
                  monthly.get('mech_1'), monthly.get('mech_0'), None]
        result.append({'warehouse': wh, 'values': [None if value is None else str(value) for value in values]})
    return result
