import pytest
from wulf_web_leader.audit.classifier import classify_website_kind


def test_classify_none():
    assert classify_website_kind(None) == "none"
    assert classify_website_kind("") == "none"
    assert classify_website_kind("   ") == "none"


def test_classify_facebook():
    assert classify_website_kind("https://www.facebook.com/hydraulikrzeszow") == "facebook"
    assert classify_website_kind("http://fb.com/salonfryzjerski") == "facebook"
    assert classify_website_kind("m.facebook.com/auto_repair") == "facebook"
    assert classify_website_kind("fb.me/mybiz") == "facebook"


def test_classify_instagram():
    assert classify_website_kind("https://www.instagram.com/dresden_friseur") == "instagram"
    assert classify_website_kind("http://instagr.am/beauty_studio") == "instagram"


def test_classify_directory():
    # Polish directories
    assert classify_website_kind("https://panoramafirm.pl/podkarpackie,rzeszów/hydraulik.html") == "directory"
    assert classify_website_kind("http://pkt.pl/firma/jan-kowalski-12345") == "directory"
    assert classify_website_kind("https://znanylekarz.pl/lekarz-weterynarii") == "directory"
    assert classify_website_kind("https://booksy.com/pl-pl/1234_barber") == "directory"
    assert classify_website_kind("https://oferteo.pl/hydraulik/rzeszow") == "directory"

    # German directories
    assert classify_website_kind("https://www.gelbeseiten.de/branche/klempner/dresden") == "directory"
    assert classify_website_kind("http://dasoertliche.de/Themen/Autowerkstatt/Dresden.html") == "directory"
    assert classify_website_kind("https://www.cylex.de/firma-home/meisterbetrieb-123.html") == "directory"


def test_classify_own():
    assert classify_website_kind("https://hydraulik-rzeszow.pl") == "own"
    assert classify_website_kind("http://www.klempnerei-mueller.de") == "own"
    assert classify_website_kind("https://autoserwis-kowalski.com.pl") == "own"
    assert classify_website_kind("friseur-dresden.de") == "own"
