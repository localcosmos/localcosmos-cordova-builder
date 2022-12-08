import os, logging
from logging.handlers import SMTPHandler

def get_logger(name, logging_folder, log_filename, smtp_logger={}):
    
    logger = logging.getLogger(name)

    if not os.path.isdir(logging_folder):
        os.makedirs(logging_folder)

    logfile_path = os.path.join(logging_folder, log_filename)

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    # add FileHandler
    file_hdlr = logging.FileHandler(logfile_path)
    file_hdlr.setFormatter(formatter)
    file_hdlr.setLevel(logging.INFO)
    logger.addHandler(file_hdlr)

    logger.setLevel(logging.INFO)

    # add smtp Handler
    if smtp_logger:
        smtp_hdlr = SMTPHandler((smtp_logger['host'], smtp_logger['port']), smtp_logger['from'], smtp_logger['to'],
                                'CordovaAppBuilder Error', credentials=smtp_logger['credentials'], secure=())

        smtp_hdlr.setLevel(logging.ERROR)
        logger.addHandler(smtp_hdlr)

    return logger
