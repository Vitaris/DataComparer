import os
import time
import numpy as np
import pandas as pd
from export_results import ExportResults
from pandas.api.types import is_numeric_dtype
from fastnumbers import query_type
import re
from copy import deepcopy


class Comparison:
    """todo"""

    def __init__(self, configuration, defaults, export_folder, log):
        self.configuration = configuration
        self.defaults = defaults
        self.export_folder = export_folder
        self.log = log
        self.summary = {'report_name': configuration['file_name'],
                        'paths': {
                            'comp_report': export_folder + '\\' + '\\' + configuration.get('file_name') + '.xlsx',
                            'file_left': configuration['left'],
                            'file_right': configuration['right']},
                        'lines': {'merged': 0, 'left': 0, 'right': 0},
                        'column_names': [],
                        'diff_column_names': [],
                        'diffs_counter': {},
                        'merge_match': {'match_both': 0, 'unmatched_left': 0, 'unmatched_right': 0},
                        'configuration': {},
                        'total_time': 0.0,
                        'note': None
                        }
        self.df_left, self.df_right, self.add_header = self.load_reports()
        self.columns = self.check_columns()
        self.df_merge = self.merge_reports()
        if not self.df_merge.empty:
            self.df_compare, self.x_columns = self.compare_reports()
            self.columns_with_diffs = self.apply_tolerances()

    def check_columns(self):
        """
        Checks that both reports contain the same columns and are in the same order
        """

        if len(self.df_left.columns) != len(self.df_right.columns):
            raise ValueError(f'No. of column of compared reports differs!')

        for i in range(len(self.df_left.columns)):
            if list(self.df_left)[i] != list(self.df_right)[i]:
                raise ValueError(f'The names of the reports columns in position {i} are different! '
                                 f' Left report has name: {list(self.df_left)[i]} '
                                 f'and right: {list(self.df_right)[i]}')
        columns = list(self.df_left)
        self.summary['column_names'].extend(columns)

        return columns

    def merge_reports(self):
        """
        Merges and sorts two dataframes in an "Outer join" way.
        """
        if self.df_left.empty and self.df_right.empty:
            message = 'Left and right reports are empty and will not be compared'
            self.log.logger.info(message)
            self.summary.update({'note': message})
            return pd.DataFrame()  # Return an empty dataframe

        if self.df_left.empty or self.df_right.empty:
            if self.df_left.empty:
                message = 'Left report is empty and will not be compared in detail'
                self.log.logger.info('Left report is empty and will not be compared in detail')
                self.summary.update({'note': message})
            else:
                message = 'Right report is empty and will not be compared in detail'
                self.log.logger.info(message)
                self.summary.update({'note': message})
            return pd.DataFrame()  # Return an empty dataframe

        self.log.logger.info(f'The number of lines in the left file is {len(self.df_left)}')
        self.log.logger.info(f'The number of lines in the right file is {len(self.df_right)}')

        start = time.perf_counter()
        df_merge = pd.merge(self.df_left, self.df_right, how='outer', on=self.configuration['references'],
                            sort=True, indicator=True)

        if max(len(self.df_left), len(self.df_right)) != len(df_merge):
            self.log.logger.warning(f'Length of input and merged tables differs!')
            self.log.logger.warning(
                f'Left = {len(self.df_left)}, right = {len(self.df_right)}, merged = {len(df_merge)}')
        self.log.logger.info(f'Merging files finished, elapsed time: {time.perf_counter() - start:0.2f}s')

        self.summary['lines'].update({'merged': len(df_merge)})

        return df_merge

    def compare_reports(self):
        """
        At this point the two reports are sorted and merged in the "df_merge" dataframe.
        For the comparison, the left and right columns need to he picked up from merged table.
        """
        columns = []
        columns_compare_left = []
        columns_compare_right = []
        tolerance_indexes = {}

        header_names = list(self.df_merge)
        for column_name in self.columns:
            if column_name in self.configuration['references']:
                columns.append([header_names.index(column_name), header_names.index(column_name)])
            else:
                columns.append(
                    [header_names.index(str(column_name) + '_x'), header_names.index(str(column_name) + '_y')])
                if column_name not in self.configuration['ignore_columns']:
                    columns_compare_left.append(header_names.index(str(column_name) + '_x'))
                    columns_compare_right.append(header_names.index(str(column_name) + '_y'))
                if column_name in self.configuration['tolerances']:
                    tolerance_indexes.update(
                        {header_names.index(str(column_name) + '_x'): self.configuration['tolerances'][column_name]})

        df_left_compare = self.df_merge.iloc[:, columns_compare_left]
        df_right_compare = self.df_merge.iloc[:, columns_compare_right]

        left_header = df_left_compare.columns.values.tolist()
        for i in range(len(left_header)):
            left_header[i] = left_header[i][:-2]

        right_header = df_right_compare.columns.values.tolist()
        for i in range(len(right_header)):
            right_header[i] = right_header[i][:-2]

        # df_left_compare.set_axis(left_header, axis=1, inplace=True)
        df_left_compare = df_left_compare.set_axis(left_header, axis=1)
        df_right_compare = df_right_compare.set_axis(right_header, axis=1)

        start = time.perf_counter()
        df_comparison = df_left_compare.compare(df_right_compare)

        if 'both' in self.df_merge._merge.values:
            both_lines = self.df_merge._merge.value_counts()['both']
            self.summary['merge_match'].update({'match_both': both_lines})

        if 'left_only' in self.df_merge._merge.values:
            left_lines = self.df_merge._merge.value_counts()['left_only']
            self.summary['merge_match'].update({'unmatched_left': left_lines})

        if 'right_only' in self.df_merge._merge.values:
            right_lines = self.df_merge._merge.value_counts()['right_only']
            self.summary['merge_match'].update({'unmatched_right': right_lines})

        self.log.logger.info(f'Dataframes comparison finished, elapsed time: {time.perf_counter() - start:0.2f}s')

        return df_comparison, columns

    def apply_tolerances(self):
        """
        The data frame self.df;comparison contains only differences, so it is effectively
        to check the differences here, not in the whole data frame
        """

        # Apply the default setting
        start = time.perf_counter()
        tolerances = deepcopy(self.configuration['tolerances'])
        for default_tolerance in self.defaults['tolerances']:
            for column in self.columns:
                column = str(column)
                name_match = re.match(default_tolerance['name'], column)
                if name_match:
                    if name_match.group() == column:
                        if column not in tolerances:
                            self.configuration['tolerances'].update(
                                {column: {'tolerance': float(default_tolerance['tolerance']),
                                          'tolerance_mode': default_tolerance['tolerance_mode']}})
                            self.log.logger.info(f'\tTolerance for column updated: {column.ljust(10)}\t\t'
                                                 f'"tolerance": {default_tolerance["tolerance"]},\t'
                                                 f'"tolerance_mode": {default_tolerance["tolerance_mode"]}')

        self.log.logger.info(f'Applying the defaults to configuration finished, '
                             f'elapsed time: {time.perf_counter() - start:0.2f}s')

        # Select the pairs of columns which have the tolerance defined
        start = time.perf_counter()
        columns_with_diffs = []
        tolerance_check = []
        unique_column = 0
        for i in range(0, len(self.df_compare.columns), 2):
            columns_with_diffs.append(self.df_compare.columns[i][0])
            if self.df_compare.columns[i][0] in self.configuration['tolerances']:
                has_tolerance = True
            else:
                has_tolerance = False

            tolerance_check.append({'has_tolerance': has_tolerance,
                                    'indexes': [i, i + 1],
                                    'unique_column': unique_column})
            unique_column += 1

        self.summary['diff_column_names'].extend(columns_with_diffs)

        # Differences counter for each column
        diffs_counter = {}
        for diff_column in columns_with_diffs:
            diffs_counter.update({diff_column: {'absolute': 0, 'in_tolerance': 0}})

        # Drop the lines where there are differences in tolerances
        if tolerance_check:
            rows_to_drop = []
            for index, line in self.df_compare.iterrows():
                drop = [False] * len(tolerance_check)
                for check in tolerance_check:
                    if pd.isna(line[check['indexes'][0]]) and pd.isna(line[check['indexes'][1]]):
                        drop[check['unique_column']] = True
                        continue
                    column_name = line.index[check['indexes'][0]][0]
                    diffs_counter[column_name]['absolute'] += 1
                    if check['has_tolerance'] is True:
                        left_val = self.check_for_number(line[check['indexes'][0]])
                        right_val = self.check_for_number(line[check['indexes'][1]])
                        if is_numeric_dtype(left_val) and is_numeric_dtype(right_val):
                            if column_name in self.configuration['tolerances']:
                                if self.configuration['tolerances'][column_name]['tolerance_mode'].lower() == 'abs':
                                    if abs(left_val - right_val) <= \
                                            self.configuration['tolerances'][column_name]['tolerance']:
                                        drop[check['unique_column']] = True
                                        diffs_counter[column_name]['in_tolerance'] += 1
                                elif self.configuration['tolerances'][column_name]['tolerance_mode'].lower() == 'rel':
                                    # check the dividing by zero!
                                    if right_val != 0:
                                        if abs(left_val - right_val) / abs(right_val) <= \
                                                self.configuration['tolerances'][column_name]['tolerance']:
                                            drop[check['unique_column']] = True
                                            diffs_counter[column_name]['in_tolerance'] += 1
                                else:
                                    raise ValueError(f'Unknown parameter for "tolerance mode": '
                                                     f'{self.configuration["tolerances"][column_name]["tolerance_mode"]}, '
                                                     f'have to be "Abs" or "Rel"')

                if False not in drop:
                    rows_to_drop.append(index)

            if rows_to_drop:
                self.log.logger.info(f'By applying the tolerances, {len(rows_to_drop)} '
                                     f'({(len(rows_to_drop) / len(self.df_compare)) * 100:0.2f}%) differences were deleted')
                self.df_compare.drop(rows_to_drop, inplace=True)

            self.summary['diffs_counter'].update(diffs_counter)
        self.summary['configuration'].update(self.configuration)
        self.log.logger.info(
            f'Applying the tolerances to comparison finished, elapsed time: {time.perf_counter() - start:0.2f}s')

        return columns_with_diffs

    @staticmethod
    def check_for_number(input_value):
        """
        The query_type function can be used if you need to determine
        if a value is one of many types, rather than whether or not it is one specific type.
        https://pypi.org/project/fastnumbers
        """
        a = query_type(input_value)
        if a in [int, np.int64]:
            return np.int64(input_value)
        elif a in [float, np.float64]:
            return np.float64(input_value)
        elif a is str:
            return input_value
        else:
            raise ValueError(f'Unknown format: {a}')

    @staticmethod
    def read_w_replace(file, sep, replace=None, r_start=None, r_end=None, ignore_r=None):
        with open(file, 'r') as reader:
            lines = reader.readlines()

            for i in range(len(lines)):
                if replace:
                    lines[i] = lines[i].replace(replace[0], replace[1])
                lines[i] = lines[i].replace(' ', '')
                lines[i] = lines[i].replace('\n', '')
                lines[i] = lines[i].lstrip(r_start)
                lines[i] = lines[i].rstrip(r_end)
                lines[i] = lines[i].split(sep)

        if ignore_r:
            del (lines[ignore_r[0]:ignore_r[-1] + 1])

        df = pd.DataFrame(lines)

        # convert first row to header:
        df.columns = df.iloc[0]
        df = df[1:]
        df.reset_index(inplace=True, drop=True)

        return df

    def load_reports(self):
        """
        todo
        """

        start = time.perf_counter()
        self.log.logger.info('')
        self.log.logger.info('  *******  Reports Comparison  *******  ')
        self.log.logger.info(f'Comparing the files started: {os.path.basename(self.configuration["left"])} '
                             f'<-> {os.path.basename(self.configuration["right"])}')

        if self.configuration["file_type"] == 'xls':
            # df_left = pd.read_excel(comparison["left"], encoding='unicode_escape')
            df_left = pd.read_excel(self.configuration["left"], 0)
            df_right = pd.read_excel(self.configuration["right"], 0)
        elif self.configuration["remove_begin"] or self.configuration["remove_end"] or self.configuration["replace"]:
            df_left = self.read_w_replace(self.configuration["left"], 'III', replace=self.configuration["replace"],
                                          r_start=self.configuration["remove_begin"],
                                          r_end=self.configuration["remove_end"],
                                          ignore_r=self.configuration["ignore_rows"])
            df_right = self.read_w_replace(self.configuration["right"], 'III', replace=self.configuration["replace"],
                                           r_start=self.configuration["remove_begin"],
                                           r_end=self.configuration["remove_end"],
                                           ignore_r=self.configuration["ignore_rows"])
        else:
            df_left = pd.read_csv(self.configuration["left"], sep=self.configuration["separator"],
                                  header=self.configuration["header"],
                                  names=self.configuration['header_names'], encoding='unicode_escape', engine='python',
                                  skiprows=self.configuration["ignore_rows"])
            if len(self.configuration['drop_duplicates']) > 0:
                df_left.drop_duplicates(subset=self.configuration['drop_duplicates'], inplace=True)

            # In case that there are no header, Cast the column number to string
            if not self.configuration["header"] and self.configuration['header_names']:
                columns_names = []
                for i in range(len(df_left.columns)):
                    columns_names.append(str(i))
                df_left.columns = columns_names

            self.log.logger.info(f'Reading file: {self.configuration["left"]} took {time.perf_counter() - start:0.2f}s')

            start = time.perf_counter()
            df_right = pd.read_csv(self.configuration["right"], sep=self.configuration["separator"],
                                   header=self.configuration["header"],
                                   names=self.configuration['header_names'], encoding='unicode_escape', engine='python',
                                   skiprows=self.configuration["ignore_rows"])

            if len(self.configuration['drop_duplicates']) > 0:
                df_right.drop_duplicates(subset=self.configuration['drop_duplicates'], inplace=True)

            # In case that there are no header, Cast the column number to string
            if not self.configuration["header"] and self.configuration['header_names']:
                columns_names = []
                for i in range(len(df_left.columns)):
                    columns_names.append(str(i))
                df_right.columns = columns_names

            self.log.logger.info(
                f'Reading file: {self.configuration["right"]} took {time.perf_counter() - start:0.2f}s')
        if self.configuration["header"] or self.configuration['header_names']:
            add_header = True
        else:
            add_header = False

        self.summary['lines'].update({'left': len(df_left)})
        self.summary['lines'].update({'right': len(df_right)})

        return df_left, df_right, add_header

    def get_comparison(self):
        return self
