import pandas as pd
import numpy as np
from xlsxwriter import Workbook
from fastnumbers import query_type
from pandas.api.types import is_numeric_dtype


class ExportResults:
    """
    Creates an object to accumulate the results through the
    testing process and writes them to an Excel file
    """

    def __init__(self, path, file_name, _log, postfix='_comparison'):
        self.log = _log
        self.workbook = Workbook(path + '\\' + file_name + postfix + ".xlsx")
        # Formats
        self.format_header = self.workbook.add_format(
            {'bg_color': '#COCGCG', 'bold': True, 'top': True, 'bottom': True})
        self.format_header_marked = self.workbook.add_format(
            {'bg_color': 'fiFFCéCé', 'bold': True, 'top': True, 'bottom': True})
        self.format_header_right = self.workbook.add_format(
            {'bg_color': '#COCOC0', 'bold': True, 'top': True, 'bottom': True})
        self.format_header_marked_right = self.workbook.add_format(
            {'bg_color': '#FFC6C6', 'bold': True, 'top': True, 'bottom': True})
        self.format_light_orange = self.workbook.add_format({'bg_color': '#FFC663'})
        self.format_light_red = self.workbook.add_format({'bg_color': '#FFC6C6'})
        self.format_light_yellow = self.workbook.add_format({'bg_color': '#FFEB9C'})
        self.format_fail = self.workbook.add_format({'bg_color': '#FFC6C6'})
        self.format_success = self.workbook.add_format({'bg_color': '#C6FFC6'})
        self.format_red_text = self.workbook.add_format({'bold': True, 'font_color': 'red'})
        self.format_green_text = self.workbook.add_format({'bold': True, 'font_color': 'green'})
        self.format_fail_second_row = self.workbook.add_format({'bg_color': '#FFC6C6', 'bottom': True})
        self.format_fail_second_cell = self.workbook.add_format({'bg_color': '#FFC6C6', 'right': True})
        self.format_second_row = self.workbook.add_format({'bottom': True})
        self.format_second_cell = self.workbook.add_format({'right': True})
        self.format_percentage = self.workbook.add_format({'num_format': '0.00%'})
        self.format_percentage_light_red = self.workbook.add_format({'bg_color': '#FFC6C6', 'num_format': '0.00%'})
        self.format_percentage_light_orange = self.workbook.add_format({'bg_color': '#FFC663', 'num_format': '0.00%'})
        self.format_seconds = self.workbook.add_format({'num_format': '0.00"s"'})

    def add_comparison_header(self, sheet, comparison, mark_names=True, add_diff_column=True, doubling_names=True,
                              add_indicator=True, left_postfix='_left', right_postfix='_right', diffs_postfix='_diffs'):
        """
        Adds header to Excel sheet
        """

        if add_diff_column is None:
            add_diff_column = []

        columns_widths = [1]
        cell = 0
        row = 0

        for column_name in comparison.columns:
            column_name = str(column_name)  # Casting to string
            if column_name in comparison.columns_with_diffs and mark_names:
                format_left = self.format_header_marked
                format_right = self.format_header_marked_right
            else:
                format_left = self.format_header
                format_right = self.format_header_right

            # Column name for "left"
            sheet.write(row, cell, column_name + left_postfix, format_left)
            columns_widths.append(len(column_name + left_postfix))
            cell += 1

            # Column name for "right"
            sheet.write(row, cell, column_name + right_postfix, format_right)
            columns_widths.append(len(column_name + right_postfix))
            cell += 1

            # Column name for "diffs"
            if column_name in comparison.configuration['count_diffs'] and add_diff_column:
                sheet.write(row, cell, column_name + diffs_postfix, self.format_header_right)
                columns_widths.append(len(column_name + right_postfix))
                cell += 1

        if add_indicator:
            sheet.write(row, cell, 'Indicator', self.format_header_right)
            columns_widths.append(len('Indicator'))
            cell += 1
        row += 1
        return columns_widths, row

    def create_detailed_report(self, comparison, limit=None):
        """
        todo
        """

        row = 0
        add_differences = comparison.configuration['count_diffs']
        results_sheet = self.workbook.add_worksheet("Detailed Comparison")

        if comparison.df_merge.empty:
            return
        results_sheet.freeze_panes(1, 0)

        # Add Header to first line
        if comparison.configuration['header'] or True:
            columns_widths, row = self.add_comparison_header(results_sheet, comparison)
        else:
            results_sheet.write(row, 0, 'No header', self.format_green_text)
            columns_widths = [12] * len(comparison.x_columns) * 2
            row += 1

        # Add the rows with differences
        for diff in comparison.df_compare.index.tolist():
            cell = 0
            for pair in comparison.x_columns:
                if comparison.df_merge.iloc[diff, -1] == 'both':
                    left_value = self.check_for_number(comparison.df_merge.iloc[diff, pair[0]])
                    right_value = self.check_for_number(comparison.df_merge.iloc[diff, pair[1]])
                elif comparison.df_merge.iloc[diff, -1] == 'left_only':
                    left_value = self.check_for_number(comparison.df_merge.iloc[diff, pair[0]])
                    right_value = ''
                else:
                    left_value = ''
                    right_value = self.check_for_number(comparison.df_merge.iloc[diff, pair[1]])
                match = False
                if type(left_value) == str and type(right_value) == str:
                    if left_value == right_value:
                        match = True
                elif is_numeric_dtype(left_value) and is_numeric_dtype(right_value):
                    if str(comparison.df_merge.columns[pair[0]]).endswith('_x') \
                            or \
                            str(comparison.df_merge.columns[pair[0]]).endswith('_y'):
                        tolerance_name = comparison.df_merge.columns[pair[0]][:-2]
                    else:
                        tolerance_name = comparison.df_merge.columns[pair[0]]
                    tolerance_config = comparison.configuration['tolerances']

                    # Get tolerance value and mode
                    if tolerance_config.get(tolerance_name):
                        tolerance_value = tolerance_config[tolerance_name]['tolerance']
                        tolerance_mode = tolerance_config[tolerance_name]['tolerance_mode']
                    else:
                        tolerance_value = 0.0
                        tolerance_mode = 'Abs'

                    # Check for difference respecting the tolerance
                    if tolerance_mode.lower() == 'abs':
                        if abs(left_value - right_value) <= tolerance_value:
                            match = True
                    elif tolerance_mode.lower() == 'rel':
                        # check the dividing by zero!
                        if right_value == 0:
                            match = False
                        elif abs(left_value - right_value) / abs(right_value) <= tolerance_value:
                            match = True

                if match:
                    results_sheet.write(row, cell, left_value)
                    results_sheet.write(row, cell + 1, right_value, self.format_second_cell)
                else:
                    results_sheet.write(row, cell, left_value, self.format_fail)
                    results_sheet.write(row, cell + 1, right_value, self.format_fail_second_cell)
                cell += 2
                # Count difference if configured
                if comparison.columns[pair[0]] in add_differences:
                    if is_numeric_dtype(left_value) and is_numeric_dtype(right_value):
                        results_sheet.write(row, cell, abs(left_value - right_value), self.format_second_cell)
                    else:
                        results_sheet.write(row, cell, 0, self.format_second_cell)
                    cell += 1
            # Add the presence indicator(left, right, both) at the end of row
            results_sheet.write(row, cell, comparison.df_merge.iloc[diff, -1])

            # New line
            row += 1

            #  Checking that the limit been reached
            if limit:
                if row >= limit:
                    results_sheet.write(row, 0,
                                        f'A limit on the number of results ({limit} comparisons) was used!',
                                        self.format_red_text)
                results_sheet.write(row, 0,
                                    f'Differences were found on '
                                    f'{len(comparison.df_compare.index.tolist())} lines of total '
                                    f'{len(comparison.df_merge)} lines, '
                                    f'{round((len(comparison.df_compare.index.tolist()) / len(comparison.df_merge)) * 100)}%',
                                    self.format_red_text)
                break

        # Set individual columns widths
        for i in range(len(columns_widths)):
            results_sheet.set_column(i, i, columns_widths[i] + 5)  # (+ 5) for space for autofilter
        # Set autofilters  for each columns + indicator column
        results_sheet.autofilter(f'A1:{self.excel_column_name(len(columns_widths) + 1)}1')

    def add_column_names(self, sheet, header, first_cell_empty=True, first_cell=''):
        """
            Adds column names to the first column, each column name to a new row
        """
        cell = 0
        row = 0
        if not first_cell_empty:
            sheet.write(row, cell, first_cell, self.format_header)
            sheet.set_column(cell, cell, self.limit(len(first_cell) + 4, minimum=8))
        row += 1
        for header_element in header:
            sheet.write(row, cell, header_element)
            sheet.set_column(cell, cell, self.limit(len(header_element) + 4, minimum=8))
            row += 1

        return row

    @staticmethod
    def limit(value, minimum=None, maximum=None):
        if minimum:
            if value < minimum:
                value = minimum

        if maximum:
            if value > maximum:
                value = maximum

        return value

    def add_diffs(self, sheet, row, column_names, summary):
        """
        todo
        """

        diff_types = ['absolute', 'in_tolerance']
        cell = 1
        row = 0
        for diff_type in diff_types:
            sheet.write(row, cell, diff_type, self.format_header)
            sheet.set_column(cell, cell, 20)
            row += 1
            for column in column_names:
                if summary['diffs_counter'].get(column):
                    sheet.write(row, cell, summary['diffs_counter'][column][diff_type])
                else:
                    sheet.write(row, cell, 0)
                row += 1
            cell += 1
            row = 0
        row = 0

        sheet.write(row, cell, "Tolerance type", self.format_header)
        sheet.set_column(cell, cell, 16)
        sheet.write_comment(row, cell, 'Rel — Relative tolerance\nAbs - Absolute tolerance')
        row += 1
        for column in column_names:
            if summary['configuration']['tolerances'].get(column):
                sheet.write(row, cell, summary['configuration']['tolerances'][column]['tolerance_mode'])
                row += 1
        row = 0
        cell += 1
        sheet.write(row, cell, "Tolerance", self.format_header)
        sheet.set_column(cell, cell, 16)
        sheet.write_comment(row, cell, 'Tolerance value')
        row += 1

        for column in column_names:
            if summary['configuration']['tolerances'].get(column):
                sheet.write(row, cell, summary['configuration']['tolerances'][column]['tolerance'])
                row += 1
        sheet.freeze_panes(1, 0)

    def create_summary(self, summary_dict):
        """
        TODO
        """
        i = 0
        row = 0

        sh = self.create_sheets(summary_dict)

        # Add columns names to header
        for name in [
            {'column_name': 'File Name', 'width': 48,
             'comment': 'Click on the file name for more detailed information'},
            {'column_name': 'Status', 'comment': '0 - Success\n100 - Failed'},
            {'column_name': 'Diffs Total', 'comment': 'Total number of differences, no tolerance applied'},
            {'column_name': 'Diffs in Tolerance', 'comment': 'The number of differences that are within tolerance'},
            {'column_name': 'Diffs out of Tolerance', 'comment': 'The number of differences that exceed the tolerance'},
            {'column_name': 'Line count left', 'comment': 'The number of lines found in the report'},
            {'column_name': 'Line count right', 'comment': 'The number of lines found in the report'},
            {'column_name': 'Match', 'width': 12, 'comment': 'Lines occurring in both compared reports'},
            {'column_name': 'Left unmatched', 'comment': 'Lines occurring only in the left report'},
            {'column_name': 'Right unmatched', 'comment': 'Lines occurring only in the right report'},
            {'column_name': 'Comparison time (s)'},
            {'column_name': 'Note', 'width': 64},
            {'column_name': 'Comparison file link'},
            {'column_name': 'Path left'},
            {'column_name': 'Path right'}
        ]:
            # Write column name
            sh['Summary_Sheet'].write(row, i, name['column_name'], self.format_header)
            # Add comment
            if name.get('comment'):
                sh['Summary_Sheet'].write_comment(row, i, name['comment'])
            # Set width for each column
            if name.get('width'):
                sh['Summary_Sheet'].set_column(i, i, name['width'])
            else:
                sh['Summary_Sheet'].set_column(i, i, len(name['column_name']) + 2)
            i += 1
        row += 1

        for status, result in summary_dict:
            if status == 0:
                cell = 0
                diffs_abs = 0
                diffs_in_tolerance = 0
                for index, column in result['diffs_counter'].items():
                    diffs_abs += column['absolute']
                    diffs_in_tolerance += column['in_tolerance']

                # Write report name and create hyperlink to its sheet
                # Background color of report name depends on number
                # of diffs in tolerance and out of tolerance.
                file_name = f'=HYPERLINK("A{result["report_name"][:31]}EA1","{result["report_name"][:31]}")'
                if diffs_abs > 0:
                    if diffs_abs == diffs_in_tolerance:
                        sh['Summary_Sheet'].write(row, cell, file_name, self.format_light_orange)
                    else:
                        sh['Summary_Sheet'].write(row, cell, file_name, self.format_light_red)
                else:
                    sh['Summary_Sheet'].write(row, cell, file_name)

                cell += 1

                # Write status
                sh['Summary_Sheet'].write(row, cell, status, self.format_success)
                cell += 1

                # Write number of diffs of comparison
                sh['Summary_Sheet'].write(row, cell, diffs_abs)
                cell += 1
                sh['Summary_Sheet'].write(row, cell, diffs_in_tolerance)
                cell += 1
                sh['Summary_Sheet'].write(row, cell, diffs_abs - diffs_in_tolerance)
                cell += 1

                # If line count does not match for both reports, an orange background will be used
                if result['lines']['left'] == result['lines']['right']:
                    sh['Summary_Sheet'].write(row, cell, result['lines']['left'])
                    cell += 1
                    sh['Summary_Sheet'].write(row, cell, result['lines']['right'])
                    cell += 1
                else:
                    sh['Summary_Sheet'].write(row, cell, result['lines']['left'], self.format_light_orange)
                    cell += 1
                    sh['Summary_Sheet'].write(row, cell, result['lines']['right'], self.format_light_orange)
                    cell += 1

                # Both, left, right
                # If line count does not match for both reports, an orange background will be used
                sh['Summary_Sheet'].write(row, cell, result['merge_match']['match_both'])
                cell += 1
                if result['merge_match']['unmatched_left'] != 0 or result['merge_match']['unmatched_left'] != 0:
                    sh['Summary_Sheet'].write(row, cell, result['merge_match']['unmatched_left'],
                                              self.format_light_red)
                    cell += 1
                    sh['Summary_Sheet'].write(row, cell, result['merge_match']['unmatched_right'],
                                              self.format_light_red)
                    cell += 1
                else:
                    sh['Summary_Sheet'].write(row, cell, result['merge_match']['unmatched_left'])
                    cell += 1
                    sh['Summary_Sheet'].write(row, cell, result['merge_match']['unmatched_right'])
                    cell += 1

                # Comparison time
                sh['Summary_Sheet'].write(row, cell, round(result['total_time'], 2))
                cell += 1

                # Note
                if result['note']:
                    sh['Summary_Sheet'].write(row, cell, result['note'])
                cell += 1

                # Comparison paths
                sh['Summary_Sheet'].write(row, cell, result['paths']['comp_report'])
                cell += 1
                sh['Summary_Sheet'].write(row, cell, result['paths']['file_left'])
                cell += 1
                sh['Summary_Sheet'].write(row, cell, result['paths']['file_right'])
                cell += 1

            elif status == 100:
                sh['Summary_Sheet'].write(row, 0, result['file_name'])
                sh['Summary_Sheet'].write(row, 1, status, self.format_fail)
                sh['Summary_Sheet'].write(row, 9, f'Failed: {result["error"]}')

            row += 1

        sh['Summary_Sheet'].autofilter(f'A1:J1')
        sh['Summary_Sheet'].freeze_panes(1, 0)

    def create_sheets(self, summary_dict):
        """
        Add the summary sheet to the front and then
        add sheets for each comparison
        """
        sheets = {'Summary_Sheet': self.workbook.add_worksheet('Summary_Sheet')}
        summary_details = []

        for status, report_summary in summary_dict:
            if status == 0:
                row = 0
                report_name = report_summary['report_name']
                report_sheet = self.workbook.add_worksheet(report_name[:31])
                row = self.add_column_names(report_sheet, report_summary['diff_column_names'], first_cell_empty=False,
                                            first_cell='=HYPERLINK("#Summary_Sheet!A1","Back to Summary")')
                self.add_diffs(report_sheet, row, report_summary['diff_column_names'], report_summary)
                sheets.update({report_name: report_sheet})
        return sheets

    @staticmethod
    def excel_column_name(n):
        """
        Number to Excel-style column name, e.g., 1 = A, 26 = Z, 27 = AA, 703 = AAA
        """
        name = ''
        while n > 0:
            n, r = divmod(n - 1, 26)
            name = chr(r + ord('A')) + name
        return name

    @staticmethod
    def check_for_number(input_value):
        """
        The query_type function can be used if you need to determine
        if a value is one of many types, rather than whether or not it is one specific type.
        https://pypi.orgg/project/fastnumbers/
        """
        value = '' if pd.isna(input_value) else input_value
        value_type = query_type(value)
        if value_type in [int, np.int64]:
            return np.int64(value)
        elif value_type in [float, np.float64]:
            return np.float64(value)
        elif value_type is str:
            return value
        else:
            raise ValueError(f'Unknown format: {value_type}')
