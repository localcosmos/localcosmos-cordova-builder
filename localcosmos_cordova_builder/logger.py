import os, logging
from logging.handlers import SMTPHandler
import smtplib

from logging.handlers import SMTPHandler
import smtplib

class SMTPSSLHandler(SMTPHandler):
    def emit(self, record):
        try:
            port = self.mailport or smtplib.SMTP_SSL_PORT
            smtp = smtplib.SMTP_SSL(self.mailhost, port, timeout=self.timeout)
            try:
                if self.username:
                    smtp.login(self.username, self.password)
                msg = self.format(record)
                smtp.sendmail(self.fromaddr, self.toaddrs, msg)
            finally:
                smtp.quit()
        except Exception:
            self.handleError(record)


def get_logger(name, logging_folder, log_filename, smtp_settings={}):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not os.path.isdir(logging_folder):
        os.makedirs(logging_folder)

    logfile_path = os.path.join(logging_folder, log_filename)

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    # Add FileHandler
    file_hdlr = logging.FileHandler(logfile_path)
    file_hdlr.setFormatter(formatter)
    file_hdlr.setLevel(logging.INFO)
    logger.addHandler(file_hdlr)

    # Add SMTPHandler
    if smtp_settings:
        credentials = (smtp_settings['credentials']['username'], smtp_settings['credentials']['password'])
        if smtp_settings['port'] == 465:
            # Use SMTP_SSL for port 465
            smtp_hdlr = SMTPSSLHandler(
                mailhost=(smtp_settings['host'], smtp_settings['port']),
                fromaddr=smtp_settings['from'],
                toaddrs=[smtp_settings['to']],
                subject='CordovaAppBuilder Error',
                credentials=credentials,
                secure=None  # SSL does not use secure=()
            )
        else:
            # Use STARTTLS for other ports (e.g., 587)
            smtp_hdlr = SMTPHandler(
                mailhost=(smtp_settings['host'], smtp_settings['port']),
                fromaddr=smtp_settings['from'],
                toaddrs=[smtp_settings['to']],
                subject='CordovaAppBuilder Error',
                credentials=credentials,
                secure=()
            )

        smtp_hdlr.setLevel(logging.ERROR)
        logger.addHandler(smtp_hdlr)

    return logger
