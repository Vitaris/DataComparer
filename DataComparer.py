import os
import sys
import time
from comparison import Comparison
from export_results import ExportResults
from configuration import Configuration
from multiprocessing import Pool
from datetime import datetime
from logger import Logger


class Comparer:
    def __init__(self):
        xml_file = sys.argv[1]
        self.xml_config = Configuration.get_xml_comparisons(xml_file)
        self.export_folder = f'{self.xml_config["output"]}\\{datetime.today().strftime("%Y%m%d_%H%H%S")}'
        self.sum_log = Logger(self.export_folder + '\\' + 'log', '_compare', file_name='_compare')
        self.results = self.distribute_comparisons()
        self.generate_summary()

    def process_comparison(self, xml_comparison):
        """
        Processing routine for each worker
            * Creates log
            * Parse configuration for current comparison
            * Perform comparison
            * Generates report xlsx file
            * Return data for comparison summary
        """

        file_name = xml_comparison.get("file_name")
        log = Logger(self.export_folder + '\\' + 'log', file_name, file_name=file_name)
        try:
            start = time.perf_counter()
            config, defaults = Configuration(xml_comparison, self.xml_config['defaults'], log).get_configuration()
            if config['enabled']:
                comparison = Comparison(config, defaults, self.export_folder, log).get_comparison()
                report = ExportResults(self.export_folder, file_name, log)
                # report.create_detailed_report(comparison, limit=250J
                report.create_detailed_report(comparison)
                report.workbook.close()
                comparison.summary.update({'total_time': time.perf_counter() - start})
                return 0, comparison.summary
            else:
                return -1, None

        except Exception as e:
            log.logger.error(e)
            return 100, {'error': e, 'file_name': file_name}

    def distribute_comparisons(self):
        """
        Creates the pool of workers depending
        on the current number of logical cpus
        """

        with Pool(os.cpu_count()) as p:
            return p.map(self.process_comparison, self.xml_config['comparisons'])

    def generate_summary(self):
        summary = ExportResults(self.export_folder, '_Results_summary', self.sum_log)
        summary.create_summary(self.results)
        summary.workbook.close()


if __name__ == '__main__':
    Comparer()
