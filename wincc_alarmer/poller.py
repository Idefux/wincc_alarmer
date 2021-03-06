""""
This module polls the wincc server periodically for alarms.
If alarms are found they are sent to the syslog server.
"""
from __future__ import print_function
from datetime import datetime, timedelta
import logging
from time import sleep

from pywincc.wincc import wincc, WinCCException
from pywincc.alarm import alarm_query_builder, AlarmRecord
from wincc_alarmer.mailer import send_alarm_email
from wincc_alarmer.syslog import syslog_message
from wincc_alarmer.config import config
import wincc_alarmer.slack as slack
import wincc_alarmer.zulip as zulip


def poll_alarms():
    """Periodically poll the server and syslog found alarms."""
    time_intervall = config.get_time_interval()
    end_time = datetime.now()
    begin_time = end_time - timedelta(seconds=time_intervall)
    host = config.get_host()
    database = config.get_database()
    wincc_instance = wincc(host, database)
    wincc_instance.connect()

    send_email = config.get_send_email()
    if send_email:
        email_priorities = config.get_email_priorities()
        email_states = config.get_email_states()

    send_syslog = config.get_send_syslog()
    if send_syslog:
        syslog_priorities = config.get_syslog_priorities()
        syslog_states = config.get_syslog_states()

    send_slack = config.get_send_slack()
    if send_slack:
        slack_priorities = config.get_slack_priorities()
        slack_states = config.get_slack_states()
        slack.read_config()

    send_zulip = config.get_send_zulip()
    if send_zulip:
        zulip_priorities = config.get_zulip_priorities()
        zulip_states = config.get_zulip_states()
        zulip.read_config()

    try:
        logging.info("Starting the while loop now.")
        logging.info("You can quit with Ctrl+C or System Exit.")
        while 1:
            try:
                query = alarm_query_builder(begin_time, end_time)
                logging.debug("Built query %s", query)
                wincc_instance.execute(query)
                alarms = wincc_instance.create_alarm_record()
                logging.debug(alarms)
                alarms_count = alarms.count_come()
                logging.info("Found %s new alarms", alarms_count)

                if send_email:
                    alarms_email = AlarmRecord(alarms.filter_by_priorities(email_priorities))
                    alarms_email = AlarmRecord(alarms_email.filter_by_states(email_states))
                    if alarms_email.count_come():
                        logging.info("Trying to send alarms email.")
                        send_alarm_email(alarms_email)

                if send_syslog:
                    alarms_syslog = AlarmRecord(alarms.filter_by_priorities(syslog_priorities))
                    alarms_syslog = AlarmRecord(alarms_syslog.filter_by_states(syslog_states))
                    if alarms_syslog.count_all():
                        logging.info("Trying to send alarms as syslog.")
                        for alarm in alarms_syslog:
                            logging.debug(alarm)
                            syslog_message(alarm)

                if send_slack:
                    alarms_slack = AlarmRecord(alarms.filter_by_priorities(slack_priorities))
                    alarms_slack = AlarmRecord(alarms_slack.filter_by_states(slack_states))
                    if alarms_slack.count_come():
                        logging.info("Trying to send slack.")
                        slack.send_alarm_slack(alarms_slack)

                if send_zulip:
                    alarms_zulip = AlarmRecord(alarms.filter_by_priorities(zulip_priorities))
                    alarms_zulip = AlarmRecord(alarms_zulip.filter_by_states(zulip_states))
                    if alarms_zulip.count_come():
                        logging.info("Trying to send zulip.")
                        zulip.send_alarm_zulip(alarms_zulip)

            except WinCCException as exc:
                print(exc)
            else:
                begin_time = end_time
                logging.info("New begin time %s", begin_time)

            logging.info("Going to sleep now for %s seconds", time_intervall)
            sleep(time_intervall)
            logging.info("I'm back from sleep.")
            end_time = datetime.now()
            logging.debug("New end_time %s", end_time)

    except (KeyboardInterrupt, SystemExit):
        logging.info("Quitting on user request.")
    finally:
        wincc_instance.close()

# if __name__ == "__main__":
#    set_debug_level()
#    poll_alarms()
