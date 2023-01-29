#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Leo Moser, Maximilian Seidler

import argparse
import yaml
import sys
import pathlib
import copy
import pprint

def build_header():
    return '# Test summary\n\n'

def build_categories(test_infos):
    content = ""

    test_infos = sorted(test_infos, key= lambda x: x['filename'])

    test_infos = sorted(test_infos, key= lambda x: x['category'])

    prioritized_categories = ['pthread', 'fork', 'exec', 'misc', 'sleep', 'usleep', 'waitpid', 'uncategorized']

    for category in prioritized_categories:
        test_infos = sorted(test_infos, key= lambda x: category in x['category'])

    current_category = None

    for test_info in test_infos:
        if current_category != test_info['category']:
            current_category = test_info['category']
            content += f'# {current_category}\n\n'

        content += f'### {test_info["filename"]}\n\n'
        content += f'Description:\n\n> {test_info["description"]}\n\n'
        content += f'Tags: '
        for tag in test_info['tags']:
            if tag != test_info['tags'][-1]:
                content += f'`{tag}`, '
            else:
                content += f'`{tag}`'
        content += '\n\n'

    return content

def build_footer():
    return 'The end.'

def main(filename):
    # Register all tests
    test_folder_path = r'userspace/tests/'
    test_files = list(pathlib.Path(test_folder_path).glob(f'test_*.c'))

    print('Starting Salsa!')
    print('Files to analyze:')
    #pprint.pprint(test_files)

    test_infos = []

    default_keys = {'category' : 'uncategorized', 'description' : 'Description missing.', 'tags' : [], 'timeout' : None}

    missing_metadata = 0

    for test_file in test_files:
        test_config_raw = ''

        with open(test_file, 'r') as f:
            test_infos.append(copy.deepcopy(default_keys))
            test_infos[-1].update({'filename' : test_file.name})

            lines = f.readlines()
            if '/*' not in  lines[0] or '#Tortillas test config' not in lines[1]:
                print(f'- Missing metadata for: {test_file.name}')
                missing_metadata = 1
                continue

            for line in lines[1:]:
                if '*/' in line:
                    break
                test_config_raw += line

            try:
                print(f'Parsing yaml from {test_file.name}')
                test_infos[-1].update(yaml.safe_load(test_config_raw))

            except yaml.YAMLError as exc:
                print("Error {}".format(exc))
                sys.exit()


    summary_content = ""

    summary_content += build_header()
    summary_content += build_categories(test_infos)
    summary_content += build_footer()

    print(f'Writing output to {filename}...')

    with open(filename, 'w') as output:
        output.write(summary_content)

    print('Done.')

    return missing_metadata

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file',
                        default='salsa_summary.md', type=str,
                        help='The filename')

    args = parser.parse_args()

    filename = args.file

    return_value = main(filename)

    if (return_value):
        print('Error: Some tests are missing metadata!')
        sys.exit(-1)
