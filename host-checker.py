#!/usr/bin/env python3

import unittest
from io import StringIO
import os

def start_ping(host):
    import subprocess
    proc = subprocess.Popen(['ping', '-c', '5', '-q', host],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc

def check_ping(host, proc):
    import re
    exitcode = proc.wait()
    stdout, stderr = proc.communicate()
    mo = re.search('([0-9]+)% packet loss', stdout.decode())
    if mo:
        if mo.group(1) != '0':
            return (False, "%s%% packet loss." % (mo.group(1)))
    return (not exitcode, "stdout: %s, stderr: %s" % (stdout, stderr) if exitcode else "")

def send_email_report(hosts, failures):
    import smtplib
    from email.mime.text import MIMEText
    msg = """HostChecker report

HostChecker has checked the following hosts:
%s

""" % "\n".join([" - %s" % host for host in hosts])
    if not failures:
        msg += "All hosts are up."
    else:
        for host in failures:
            msg += " - %s failed with the following error: %s\n" % (host, failures[host])
    msg += "\n\nBest regards,\nHostChecker"
    mimetext = MIMEText(msg)
    mimetext['Subject'] = "HostChecker report"
    mimetext['From'] = "HostChecker at argabuthon <erikalds@argabuthon.dyndns.org>"
    mimetext['To'] = "Erik Sund <erikalds@argabuthon.dyndns.org>"
    print("Sending message: %s" % mimetext)

    import subprocess
    proc = subprocess.Popen(["/usr/sbin/sendmail", "erikalds@argabuthon.dyndns.org"], stdin=subprocess.PIPE)
    proc.stdin.write(str(mimetext).encode('utf-8'))
    proc.stdin.close()
    if proc.wait():
        raise Exception("sendmail failed.")


class Config:
    def __init__(self):
        self._hosts = []
        self._recipients = []

    def hosts(self):
        return self._hosts

    def recipients(self):
        return self._recipients

    def read_file(self, fp):
        from configparser import ConfigParser
        parser = ConfigParser()
        parser.read_file(fp)
        if 'General' in parser:
            hostsline = parser['General'].get('Hosts', '')
            if hostsline:
                self._hosts = [h.strip() for h in hostsline.split(",")]
            recipients = parser['General'].get('Recipients')
            if recipients:
                self._recipients = [r.strip() for r in recipients.split(",")]

    def read_argv(self, argv):
        import argparse
        parser = argparse.ArgumentParser(description="Check if hosts are alive")
        parser.add_argument('-H', '--hosts', dest='hosts', required=False,
                            type=lambda s : [x.strip() for x in s.split(",")],
                            help='Comma separated list of hostnames to check')
        parser.add_argument('-r', '--recipients', dest='recipients',
                            type=lambda s : [x.strip() for x in s.split(",")],
                            help='Comma separated list of recipients to receive'
                                 ' e-mail notifications')
        arguments = parser.parse_args(argv[1:])
        if arguments.hosts:
            self._hosts = arguments.hosts
        if arguments.recipients:
            self._recipients = arguments.recipients

class ConfigTest(unittest.TestCase):
    def test_read_host_from_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=host.domain.com"""))
        self.assertEqual(['host.domain.com'], config.hosts())
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=anotherhost.domain.com"""))
        self.assertEqual(['anotherhost.domain.com'], config.hosts())

    def test_read_hosts_from_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=host.domain.com, anotherhost.domain.com"""))
        self.assertSetEqual(set(['host.domain.com', 'anotherhost.domain.com']),
                            set(config.hosts()))

    def test_second_read_overwrites_first(self):
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=host.domain.com"""))
        config.read_file(StringIO("""[General]
Hosts=anotherhost.domain.com"""))
        self.assertEqual(['anotherhost.domain.com'], config.hosts())

    def test_handles_missing_hosts(self):
        config = Config()
        config.read_file(StringIO("[General]\nRecipients=a@b.com"))
        self.assertEqual([], config.hosts())

    def test_missing_hosts_does_not_override(self):
        config = Config()
        config.read_file(StringIO("[General]\nHosts=b.com"))
        config.read_file(StringIO("[General]\nRecipients=a@b.com"))
        self.assertEqual(['b.com'], config.hosts())

    def test_reads_short_host_from_argv(self):
        config = Config()
        config.read_argv('host-checker.py -H host.domain.com'.split())
        self.assertEqual(['host.domain.com'], config.hosts())

    def test_reads_long_host_from_argv(self):
        config = Config()
        config.read_argv('host-checker.py --hosts anotherhost.domain.com'.split())
        self.assertEqual(['anotherhost.domain.com'], config.hosts())

    def test_argv_overrides_config_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=h0.d.com, h1.d.com"""))
        config.read_argv('host-checker.py --hosts host.dom.com'.split())
        self.assertEqual(['host.dom.com'], config.hosts())

    def test_argv_missing_hosts_does_not_override_config_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=h0.d.com, h1.d.com"""))
        config.read_argv('host-checker.py'.split())
        self.assertSetEqual(set(['h0.d.com', 'h1.d.com']), set(config.hosts()))

    def test_reads_multiple_hosts_from_argv(self):
        config = Config()
        config.read_argv('prog -H h0.d.com,h1.d.com,h2.d.com'.split())
        self.assertSetEqual(set('h0.d.com h1.d.com h2.d.com'.split()),
                            set(config.hosts()))

    def test_handles_multiple_hosts_from_argv_with_spaces(self):
        config = Config()
        config.read_argv(['prog', '-H', 'h0.d.com, h1.d.com, h2.d.com'])
        self.assertSetEqual(set('h0.d.com h1.d.com h2.d.com'.split()),
                            set(config.hosts()))

    def test_reads_mail_recipients_from_config_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Recipients=Erik Åldstedt Sund <erikalds@gmail.com>"""))
        self.assertListEqual(['Erik Åldstedt Sund <erikalds@gmail.com>'],
                             config.recipients())
        config.read_file(StringIO("""[General]
Recipients=erikalds@gmail.com"""))
        self.assertListEqual(['erikalds@gmail.com'], config.recipients())

    def test_reads_comma_separated_list_of_mail_recipients(self):
        config = Config()
        config.read_file(StringIO("""[General]
Recipients=Hei Hå <hei.haa@gmail.com>,Ha Det <ha.det@gmail.com>"""))
        self.assertSetEqual(set(['Hei Hå <hei.haa@gmail.com>',
                                 'Ha Det <ha.det@gmail.com>']),
                            set(config.recipients()))

    def test_strips_spaces_from_list_of_recipients(self):
        config = Config()
        config.read_file(StringIO("""[General]
Recipients= Hei Hå <hei.haa@gmail.com> , Ha Det <ha.det@gmail.com> """))
        self.assertSetEqual(set(['Hei Hå <hei.haa@gmail.com>',
                                 'Ha Det <ha.det@gmail.com>']),
                            set(config.recipients()))

    def test_handles_missing_recipients_from_config_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Hosts=google.com"""))
        self.assertListEqual([], config.recipients())

    def test_missing_recipients_does_not_override(self):
        config = Config()
        config.read_file(StringIO("""[General]
Recipients=e@b.com"""))
        config.read_file(StringIO("""[General]
Hosts=google.com"""))
        self.assertListEqual(['e@b.com'], config.recipients())

    def test_reads_short_recipients_from_argv(self):
        config = Config()
        config.read_argv('prog -r a@b.com'.split())
        self.assertEqual(['a@b.com'], config.recipients())

    def test_reads_long_recipients_from_argv(self):
        config = Config()
        config.read_argv('prog --recipients a@b.com'.split())
        self.assertEqual(['a@b.com'], config.recipients())

    def test_reads_another_recipient_from_argv(self):
        config = Config()
        config.read_argv('prog -r b@a.com'.split())
        self.assertEqual(['b@a.com'], config.recipients())

    def test_reads_comma_separated_recipients_from_argv(self):
        config = Config()
        config.read_argv('prog -r b@a.com,a@b.com'.split())
        self.assertSetEqual(set(['a@b.com', 'b@a.com']),
                            set(config.recipients()))

    def test_reads_comma_separated_recipients_with_spaces_from_argv(self):
        config = Config()
        config.read_argv(['prog', '-r', ' b@a.com , a@b.com '])
        self.assertSetEqual(set(['a@b.com', 'b@a.com']),
                            set(config.recipients()))

    def test_argv_recipients_overrides_config_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Recipients=a@b.com"""))
        config.read_argv('prog -r b@a.com'.split())
        self.assertEqual(['b@a.com'], config.recipients())

    def test_missing_argv_recipients_does_not_override_config_file(self):
        config = Config()
        config.read_file(StringIO("""[General]
Recipients=a@b.com"""))
        config.read_argv('prog --hosts a.com'.split())
        self.assertEqual(['a@b.com'], config.recipients())



def main(argv):
    if '--unittest' in argv:
        argv.remove('--unittest')
        return unittest.main()

    config = Config()
    for filename in ('/etc/host-checker', '~/.host-checker'):
        if os.path.exists(filename):
            with open(filename, 'r') as fp:
                config.read_file(fp)

    config.read_argv(argv)

    hosts = config.hosts()

    ping_procs = dict([(host, start_ping(host)) for host in hosts])
    failures = dict()
    for host in ping_procs:
        success, msg = check_ping(host, ping_procs[host])
        if not success:
            print("Check host %s failed: %s" % (host, msg))
            failures[host] = msg
        else:
            print("Host %s is alive" % host)

    send_email_report(hosts, failures)
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
