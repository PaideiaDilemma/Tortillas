import logging
from tortillas.log_parser import LogParser
from tortillas.tortillas_config import ParseConfigEntry


def test_log_splitting():
    config_entry = ParseConfigEntry(label='test',
                                    scope='SYSCALL',
                                    pattern=r'(.*)').compile_pattern()

    log_parser = LogParser(log_file_path='./tests/assets/out_log.txt',
                           logger=logging.getLogger(),
                           config=[config_entry])

    log_data = log_parser.parse()

    assert config_entry.label in log_data
    assert ('Syscall::EXIT: called, exit_code: 1237619379\n'
            in log_data[config_entry.label])


def test_parsing_int_splitting():
    config_entry = ParseConfigEntry(label='test',
                                    scope='SYSCALL',
                                    pattern=r'exit_code: (\d+)')
    config_entry.compile_pattern()

    log_parser = LogParser(log_file_path='./tests/assets/out_log.txt',
                           logger=logging.getLogger(),
                           config=[config_entry])

    log_data = log_parser.parse()

    assert config_entry.label in log_data
    assert '1237619379' in log_data[config_entry.label]


def test_mutliple_config_entries():
    config = [
            ParseConfigEntry(label='a', scope='SYSCALL',
                             pattern='(.*)'),
            ParseConfigEntry(label='b', scope='THREAD',
                             pattern='(kill: (.*))'),
            ParseConfigEntry(label='c', scope='PAGEFAULT',
                             pattern=r'(Address:\s+0x[0-9a-fA-F]+)')]

    for entry in config:
        entry.compile_pattern()

    log_parser = LogParser(log_file_path='./tests/assets/out_log.txt',
                           logger=logging.getLogger(),
                           config=config)

    log_data = log_parser.parse()

    for entry in config:
        assert entry.label in log_data.keys()

    assert any('kill' in log for log in log_data['b'])
    assert 'Address:          0x8006000' in log_data['c']
