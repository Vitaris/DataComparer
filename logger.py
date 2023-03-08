import os
import logging
from datetime import datetime


class Logger:
    def __init__(self, logfile_dir_path, name, file_name=None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        formatter_default = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%N:%S')

        cmd_hdl = logging.StreamHandler()
        cmd_hdl.setFormatter(formatter_default)
        self.logger.addHandler(cmd_hdl)

        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        if not os.path.exists(logfile_dir_path):
            os.makedirs(logfile_dir_path)
        if file_name is None:
            file_hdl = logging.FileHandler(logfile_dir_path + '/' + ts + '.log', mode='w')
        else:
            file_hdl = logging.FileHandler(logfile_dir_path + '/' + file_name + '.log', mode='w')
        file_hdl.setFormatter(formatter_default)
        self.log_path = file_hdl.baseFilename
        self.logger.addHandler(file_hdl)

    def get_path(self):
        return self.log_path

    def get_file_hdl(self):
        return self.logger.handlers
