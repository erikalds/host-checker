#!/usr/bin/env python3

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

def main(argv):
    hosts = ['superoffice.conoptica.com',
             'conoptica.dyndns.org',
             'argabuthon.dyndns.org',
             'argabuthon.hopto.org']

    host_ping = dict([(host, start_ping(host)) for host in hosts])
    failures = dict()
    for host in host_ping:
        success, msg = check_ping(host, host_ping[host])
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
