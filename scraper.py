# -*- coding: UTF-8 -*-

import scraperwiki
import json
from BeautifulSoup import BeautifulSoup
import datetime
import dateutil.parser
import lxml.html
import resource
import sys
import urlparse
import re
import string
import HTMLParser

# Make sure Scraperwiki believe this is the source from this database
baseurl = "http://www.mattilsynet.no/om_mattilsynet/offentlig_journal_og_innsyn/"
roothtml = scraperwiki.scrape(baseurl)

lazycache=scraperwiki.swimport('lazycache')
postlistelib=scraperwiki.swimport('postliste-python-lib')

agency = 'Mattilsynet'

def report_errors(errors):
    if 0 < len(errors):
        print "Errors:"
        for e in errors:
            print e
        raise ValueError("Something went wrong")

def out_of_cpu(arg, spent, hard, soft):
    report_errors(arg)

# Based on http://stackoverflow.com/questions/13122353/parsing-html-using-lxml-html
def entry_by_hr(parent):
    paralist = []
    para = lxml.html.etree.Element('entry')
    if parent.text:
        para.text = parent.text
    for item in parent:
        if item.tag=='hr':
            paralist.append(para)
            para = lxml.html.etree.Element('entry')
            if item.tail:
                para.text = item.tail
        else:
            para.append(item)
    return paralist

def process_list(parser, url):
    html = postlistelib.fetch_url_harder(url)
    #print html
    hp = HTMLParser.HTMLParser()
    root = lxml.html.fromstring(hp.unescape(html.decode('utf-8')))

    period = root.cssselect("head title")
    print period[0].text_content()
    matchObj = re.match( r'.*Periode (\d{2}.\d{2}.\d{4})\s*\D*\s* (\d{2}.\d{2}.\d{4}) .*', period[0].text_content(), re.M|re.I)
#Periode 23.09.2013 - 29.09.2013 Oslo
#Periode 29.07.2013 – 04.08.2013
    if matchObj: # Fake recorddate
        recorddate = dateutil.parser.parse(matchObj.group(2), dayfirst=True)
        print "match", recorddate
    subset = root.cssselect("div#articleContent")
    #print subset[0].text_content()
    savelist = []

    for entry in entry_by_hr(subset[0]):
        estr = lxml.html.etree.tostring(entry)
        if -1 != estr.find("Offentlig journal"):
            continue
#        print estr
        lines = estr.split("<br/>")
#        print lines
        if '' == lines[1]:
            del lines[1]
        meta = lines[1].split(" ")
#        print meta
        docdate = dateutil.parser.parse(meta[5], dayfirst=True)
        doctype = meta[1]

        matchObj = re.match( r'(\d+)/(\d+)\s*-\s*(\d+)$', meta[0], re.M|re.I)
        if matchObj:
            caseyear = matchObj.group(1)
            caseseqnr = matchObj.group(2)
            casedocseq = matchObj.group(3)
            caseid = str(caseyear) + "/" + str(caseseqnr)
        else:
            print "error: invalid saksnr: " + meta[0]
        arkivnr = meta[9]
        saksbehandler = meta[13].strip()
        saksansvarligenhet, saksansvarlig = saksbehandler.split('/')
        exemption = None
        for row in lines[2:-1]:
#            print "R: ", row
            rowtype, rest = row.split(":", 1)
            if 'Til' == rowtype or 'Fra' == rowtype:
                fratil = hp.unescape(string.join(row.split(" ")[1:], " "))
                fratilfield = {
                    'Til' : 'recipient',
                    'Fra' : 'sender',
                }[rowtype]
            elif 'Dok' == rowtype:
                docdesc = hp.unescape(rest.strip())
            elif 'Sak' == rowtype:
                casedesc = hp.unescape(rest.strip())
            elif 'U.off' == rowtype:
                if -1 != row.find('Grad: UO'):
                    gradert = hp.unescape(row)
                    exemption = gradert.split(':')[1].strip()
#                    print gradert, exemption
            elif 'Lnr' == rowtype:
#                print rest
                laapenr =  rest.strip().split(" ")[0].strip()
#                print laapenr
                journalseqnr, journalyear = laapenr.split("/")
                journalid = str(journalyear) + "/" + str(journalseqnr)
            else:
                raise Exception("unhandled type")

        data = {
            'agency' : parser.agency,
            'recorddate' : recorddate.date(),
            'docdate' : docdate.date(),
            'docdesc' : docdesc,
            'casedesc' : casedesc,

            'caseyear' : int(caseyear),
            'caseseqnr' : int(caseseqnr),
            'casedocseq' : int(casedocseq),
            'caseid' : caseid,
            'doctype' : doctype,

            'journalseqnr' : int(journalseqnr),
            'journalyear' : int(journalyear),
            'journalid' : journalid,
            fratilfield : fratil,

            'saksbehandler' : saksbehandler,
            'saksansvarlig' : saksansvarlig.strip(),
            'saksansvarligenhet' : int(saksansvarligenhet.strip()),


            'arkivnr' : arkivnr,
            'laapenr' : laapenr,
            'exemption' : exemption,

            'scrapedurl' : url,
            'scrapestamputc' : datetime.datetime.now()
        }

#        print data
        parser.verify_entry(data)
        savelist.append(data)
#        return # debug
    scraperwiki.sqlite.save(data=savelist, unique_keys=['caseyear', 'caseseqnr', 'casedocseq'])
    return

def fetch_urls_list(parser, baseurl, roothtml):
    root = lxml.html.fromstring(roothtml)
    subset = root.cssselect("ul.listContainer")
#    print subset[0].text_content()
    urllist = []
    for list in subset:
        urls = list.cssselect("li a")
        for ahref in urls:
            href = ahref.attrib['href']
            #print href
            newurl = urlparse.urljoin(baseurl, href)
            urllist.append(newurl)
    return urllist

def test(parser):
    url = "http://www.mattilsynet.no/om_mattilsynet/offentlig_journal_og_innsyn/bvt/periode_29072013__04082013_buskerud_vestfold_og_telemark"
    process_list(parser, url)

errors = []
parser = postlistelib.JournalParser(agency=agency)

if False:
    test(parser)
    exit(0)

urls = fetch_urls_list(parser, baseurl, roothtml)
for url in urls:
    try:
        res = scraperwiki.sqlite.select("scrapedurl from swdata where scrapedurl = '"+url+"' limit 1")
        if 0 < len(res):
            continue
    except Exception, e: # Ignore it if the table is missing
        pass
    print "Processing ", url
    try:
        process_list(parser, url)
    except Exception, e:
        print "Unable to process ", url, e
        pass
report_errors(errors)

