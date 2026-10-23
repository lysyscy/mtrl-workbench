"""Ticket behavior against isolated temporary files; no application or DB writes."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/oneoff'))
import tail_common as C
import _tail_open as O
import _tail_close as X
import _list_tails as L


@pytest.fixture
def repo(tmp_path):
    tracker=tmp_path/'tracker.md'
    tracker.write_bytes(b'# fixture\r\nTAIL_LAST_ISSUED: 20\r\n')
    tickets=tmp_path/'tickets'; tickets.mkdir()
    return tracker,tickets


def ticket(tickets, number, state, pre='None'):
    p=tickets/f'TAIL-{number}-fixture.md'
    p.write_text(f'# TAIL-{number}: fixture\n\n**What to build:** fixture\n\n'
                 f'**Blocked by:** {pre}\n\n**Status:** {state}\n\n'
                 '- [ ] independently verifiable\n\n## Comments\n',encoding='utf-8')
    return p


def args(repo,pre='None'):
    tracker,tickets=repo
    return ['--tracker',str(tracker),'--tickets',str(tickets),'--what','new',
            '--pre',pre,'--acceptance','real result']


def test_dry_run_and_no_number_reuse(repo):
    tracker,tickets=repo
    before=tracker.read_bytes()
    assert O.main(args(repo))==0
    assert tracker.read_bytes()==before and not list(tickets.iterdir())
    with pytest.raises(ValueError,match='above highwater'):
        O.main(args(repo)+['--id','19','--apply'])
    assert O.main(args(repo)+['--apply'])==0
    assert C.highwater(tracker.read_text(encoding='utf-8'),C.read_tickets(tickets))==21
    assert b'\r\n' in tracker.read_bytes()
    next(tickets.iterdir()).unlink()
    O.main(args(repo)+['--apply'])
    assert list(tickets.glob('TAIL-22-*'))


@pytest.mark.parametrize('line',['','TAIL_LAST_ISSUED: x','TAIL_LAST_ISSUED: 20\nTAIL_LAST_ISSUED: 21',
                                  'TAIL_LAST_ISSUED: -1','TAIL_LAST_ISSUED : 20'])
def test_missing_invalid_or_duplicate_highwater_refused(repo,line):
    tracker,tickets=repo
    tracker.write_text(line,encoding='utf-8')
    before=tracker.read_bytes()
    with pytest.raises(ValueError): O.main(args(repo)+['--apply'])
    assert tracker.read_bytes()==before and not list(tickets.iterdir())


def test_missing_dependency_and_wontfix_do_not_unlock(repo):
    tracker,tickets=repo
    with pytest.raises(ValueError,match='missing prerequisite'): O.main(args(repo,'TAIL-9'))
    p=ticket(tickets,9,'wontfix')
    O.main(args(repo,'TAIL-9')+['--apply'])
    assert C.read_tickets(tickets)[21][2]=='blocked'
    assert L.main(['--tickets',str(tickets)])==0
    assert C.dependency_state([9],C.read_tickets(tickets))==['TAIL-9=wontfix']
    p.write_text(p.read_text(encoding='utf-8').replace('wontfix','done'),encoding='utf-8')
    assert C.dependency_state([9],C.read_tickets(tickets))==[]
    O.main(args(repo,'TAIL-9')+['--apply'])
    assert C.read_tickets(tickets)[22][2]=='ready-for-agent'
    assert p.exists()  # a live prerequisite remains readable; open/close never purge it


def test_duplicate_ticket_number_refused(repo):
    tracker,tickets=repo
    p=ticket(tickets,9,'done')
    (tickets/'TAIL-9-other.md').write_bytes(p.read_bytes())
    with pytest.raises(ValueError,match='duplicate'): O.main(args(repo))


def test_publish_failure_restores_both_originals(repo,monkeypatch):
    tracker,tickets=repo
    before=tracker.read_bytes()
    original=Path.replace
    def fail_tracker(source,target):
        if Path(target)==tracker: raise OSError('fixture publish refused')
        return original(source,target)
    monkeypatch.setattr(Path,'replace',fail_tracker)
    with pytest.raises(OSError,match='publish refused'): O.main(args(repo)+['--apply'])
    assert tracker.read_bytes()==before and not list(tickets.iterdir())
    assert not list(tracker.parent.rglob('.tail-*'))


def test_close_keeps_real_evidence_and_dry_run_is_read_only(repo,monkeypatch):
    tracker,tickets=repo
    p=ticket(tickets,9,'ready-for-agent')
    original=p.read_bytes()
    command=['--tickets',str(tickets),'--id','9','--status','done','--reason','isolated verification passed']
    X.main(command)
    assert p.read_bytes()==original
    replace=Path.replace
    def fail(source,target): raise OSError('fixture write refused')
    with monkeypatch.context() as patch:
        patch.setattr(Path,'replace',fail)
        with pytest.raises(OSError): X.main(command+['--apply'])
    assert p.read_bytes()==original
    X.main(command+['--apply'])
    assert C.read_tickets(tickets)[9][2]=='done'
    assert 'isolated verification passed' in p.read_text(encoding='utf-8')
    assert '- [ ] independently verifiable' in p.read_text(encoding='utf-8')
    assert p.exists() and set(tracker.parent.iterdir())=={tracker,tickets}
