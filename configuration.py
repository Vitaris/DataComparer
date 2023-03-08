import os
import re
import xml.etree.ElementTree as ET

true_values = [True, 'True', 'true', 'Y', 'y', '1']
false_values = [False, 'False', 'false', 'F', 'f', '0']
none_values = [None, 'None', 'none', 'NAN', 'NaN', 'nan']


class Configuration:
    """
    Reads a xml comparison file and creates
    a list of separate comparisons with all the details
    to be processed
    """

    def __init__(self, xml_comparison, xml_defaults, log):
        self.log = log
        self.tags = {'left': {'mandatory': 'True'},
                     'right': {'mandatory': 'True'},
                     'separator': {},
                     'header': {'default': 'infer'},
                     'file_type': {'default': 'csv', 'options': ['csy', 'xls', 'db']},
                     'header_names': {'t0_list': True},
                     'columns': {'mandatory': 'True'},
                     'remove_begin': {},
                     'remove_end': {},
                     'replace': {},
                     'ignore_rows': {'to_list': True, 'cast': int},
                     'count_difference': {}}
        self.comparison_config, self.defaults = self.read_configuration(xml_comparison, xml_defaults)
        if self.comparison_config['enabled'] in true_values:
            self.process_comparison()
            self.log_config_summary()
            self.apply_defaults()

    def log_config_summary(self):
        self.log.logger.info(' ******* Configuration summary ******* ')
        for key, value in self.comparison_config.items():
            self.log.logger.info(f'\t{(key + ":").ljust(20)}\t\t{value}')

    def get_configuration(self):
        return self.comparison_config, self.defaults

    def read_configuration(self, xml_comparison, xml_defaults):
        config = {}
        if xml_comparison.find('enabled').text in true_values:
            config.update({'enabled': True})
            config.update({'file_name': xml_comparison.get('file_name')})
            for tag in self.tags:
                config.update({tag: self.get_tag_content(xml_comparison, tag)})
        elif xml_comparison.find('enabled').text in false_values:
            config.update({'enabled': False})
        else:
            raise ValueError(f'Enabled has an unknown value, it should be true or false!')

        # Read defaults section
        defaults = {}
        default_tolerances = []
        for column in xml_defaults[0].find('tolerances').findall('column'):
            default_tolerances.append({'name': column.get('name'),
                                       'tolerance': column.get('tolerance'),
                                       'tolerance_mode': column.get('tolerance_mode')})
        defaults.update({'tolerances': default_tolerances})

        return config, defaults

    @staticmethod
    def get_tag_content(comparison, tag):
        xml_element = comparison.find(tag)

        if xml_element is not None:
            if len(xml_element) == 0:
                return xml_element.text
            else:
                return xml_element
        else:
            return None

    def process_column_tags(self, config_section, ):
        """
        Checks all columns specified in the "columns" tag and collects all specifications

        example:
            <columns>
                <column name="0" reference="True" />
                <column name="1" reference="True" />
                <column name="2" reference="True" />
                <column name="3" reference="True" />
                <column name="4" tolerance="1.0" tolerance_mode="Abs" />
                <column name="5" tolerance="1.0" tolerance_mode="Rel" />
                <column name="é" drop_duplicates="True" />
                <column name="7" ignore="True" />
            </columns>
        """

        names = []
        tolerances = {}
        references = []
        ignores = []
        drops = []
        count_diffs = []

        for column in config_section['columns'].findall('column'):
            # Get name of column
            name = column.get('name')
            if name is None:
                self.log.logger.info(f'Todo, Name value is missing!')
                raise ValueError(f'Todo, Name value is missing!')
            else:
                if config_section['header'] is None:
                    if name.isdigit():
                        name = int(name)
                    else:
                        self.log.logger.info(f'Todo, If set to "no header", the column name must be the column number, '
                                             f'not the column title')
                        raise ValueError(f'Todo, If set to "no header", the column name must be the column number, '
                                         f'not the column title')

                names.append(name)

            # Check for Reference attribute
            reference = column.get('reference')
            if reference is not None:
                if reference in true_values:
                    references.append(name)

            # Check for Ignore attribute
            ignore = column.get('ignore')
            if ignore is not None:
                if ignore in true_values:
                    ignores.append(name)

            # Check for Tolerance attribute
            tolerance = column.get('tolerance')
            if tolerance is not None:
                try:
                    tolerance = float(tolerance)
                except ValueError:
                    self.log.logger.info(f'Todo, the tolerance attribute must have a numeric value!')
                    raise ValueError(f'Todo, the tolerance attribute must have a numeric value!')
                tolerance_mode = column.get('tolerance_mode')
                if tolerance_mode is None:
                    tolerance_mode = 'abs'
                elif tolerance_mode.lower() not in ['abs', 'rel']:
                    self.log.logger.info(f'Todo, the tolerance_mode attribute must be "abs" or "rel"!')
                    raise ValueError(f'Todo,the tolerance_mode attribute must be "abs" or "rel"!')

                tolerances.update({str(name): {'tolerance': tolerance,
                                               'tolerance_mode': tolerance_mode}})

            # Check for "drop_duplicates" attribute
            drop_duplicates = column.get('drop_duplicates')
            if drop_duplicates is not None:
                if drop_duplicates in true_values:
                    drops.append(name)

            # Check for "count_difference" attribute
            count_diff = column.get('count_difference')
            if count_diff is not None:
                if count_diff in true_values:
                    count_diffs.append(name)

        return [references, ignores, tolerances, drops, count_diffs]

    def check_value(self, config, key):
        value = config[key]
        if value is None:
            if 'mandatory' in self.tags[key]:
                self.log.logger.info(f'Mandatory tag "{key}" was not found!')
                raise ValueError(f'Mandatory tag "{key}" was not found!')
            elif 'default' in self.tags[key]:
                value = self.tags[key]['default']
            else:
                return value

        if 'options' in self.tags[key]:
            if value not in self.tags[key]['options']:
                self.log.logger.info(f'The tag value "{key}" was not found in allowed options! The available '
                                     f'options are: {self.tags[key]["options"]}')
                raise ValueError(f'The tag value "{key}" was not found in allowed options! The available options are: '
                                 f'{self.tags[key]["options"]}')

        if 'to_list' in self.tags[key]:
            if self.tags[key]['to_list'] is True:
                value = value.split(';')

        if 'cast' in self.tags[key]:
            if self.tags[key]['cast'] == int:
                if len(value) == 1:
                    value = int(value)
                elif len(value) > 1:
                    for i in range(len(value)):
                        value[i] = int(value[i])
        return value

    def process_comparison(self):
        """
        todo
        """
        self.comparison_config['file_type'] = self.check_value(self.comparison_config, 'file_type')

        self.comparison_config['header'] = self.check_value(self.comparison_config, 'header')
        if self.comparison_config['header'] in false_values or self.comparison_config['header'] in none_values:
            self.comparison_config['header'] = None

        ref, ignore, tol, drops, c_diffs = self.process_column_tags(self.comparison_config)
        self.comparison_config.update(
            {'references': ref, 'ignore_columns': ignore, 'tolerances': tol, 'drop_duplicates': drops,
             'count_diffs': c_diffs})
        self.comparison_config['ignore_rows'] = self.check_value(self.comparison_config, 'ignore_rows')
        self.comparison_config['header_names'] = self.check_value(self.comparison_config, 'header_names')
        del self.comparison_config['columns']

    @staticmethod
    def get_key_list(config_section, key, default=None, split=None, cast=None, mandatory=False):
        try:
            key_value = config_section[key]

        except KeyError:
            key_value = default

        # split handling
        if type(key_value) == str and split:
            key_value = key_value.split(split)

        if not cast:
            pass
        elif cast == bool:
            for i in range(len(key_value)):
                if key_value[i] in true_values:
                    key_value[i] = True
                elif key_value[i] in false_values:
                    key_value[i] = False
                else:
                    raise ValueError(f'Element {i} of {key} contains neither "True" nor "False" values')

        elif cast == int:
            for i in range(len(key_value)):
                key_value[i] = int(key_value[i])
        elif cast == float:
            for i in range(len(key_value)):
                key_value[i] = float(key_value[i])
        else:
            raise ValueError(f'Unsupported cast Value, current: {cast}, required: bool, int, float')

        if not key_value and mandatory:
            raise ValueError(f'Hissing value for "{key}" key!')
        return key_value

    @staticmethod
    def get_key_dict(config_section, key, default=None, cast=None):
        try:
            key_value = config_section[key]
        except KeyError:
            key_value = default

        if not (type(key_value) == dict):
            raise ValueError(f'Wrong input data type, {config_section}, {key}: {type(key_value)}, '
                             f'required "dict"')

    def get_key_value(self, config_section, key, default=None, cast=None, mandatory=False, options=None):
        try:
            key_value = config_section[key]
        except KeyError:
            key_value = default

        if cast == bool:
            if key_value in ['True', 'true', 'Y', 'y', '1']:
                key_value = True
            elif key_value in ['False', 'false', 'F', 'f', '0']:
                key_value = False
            else:
                key_value = None
        elif cast == float:
            key_value = float(key_value)
        elif cast == int:
            key_value = int(key_value)

        if key_value in none_values:
            key_value = None

        if not key_value and mandatory:
            raise ValueError(f'Hissing value for "{key}" key!')

        if options:
            if key_value not in options:
                raise ValueError(f'Key value not in option list!')

        self.log.logger.info(f'{key} = {key_value}')
        return key_value

    def apply_defaults(self):
        pass

    @classmethod
    def get_xml_comparisons(cls, config_file):
        root = cls.create_root(config_file)
        return {'comparisons': root.findall('comparison'),
                'output': root.find('output').text,
                'defaults': root.findall('defaults')}

    @classmethod
    def create_root(cls, config_file):
        if not os.path.isfile(config_file):
            raise FileNotFoundError(
                f'Configuration file: {os.path.abspath(config_file)} was not found!')
        return ET.parse(config_file).getroot()
