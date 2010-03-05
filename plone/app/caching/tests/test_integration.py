import pkg_resources

import unittest

#import datetime
#import dateutil.parser
#import dateutil.tz

from Products.PloneTestCase.ptc import FunctionalTestCase
from Products.PloneTestCase.ptc import default_user, default_password

from plone.app.caching.tests.layer import Layer

from Products.Five.testbrowser import Browser
import OFS.Image

from zope.component import getUtility

from zope.globalrequest import setRequest

from plone.registry.interfaces import IRegistry
from plone.caching.interfaces import ICacheSettings
from plone.cachepurging.interfaces import ICachePurgingSettings
from plone.cachepurging.interfaces import IPurger
from plone.app.caching.interfaces import IPloneCacheSettings

TEST_IMAGE = pkg_resources.resource_filename('plone.app.caching.tests', 'test.gif')
TEST_FILE = pkg_resources.resource_filename('plone.app.caching.tests', 'test.gif')


class TestOperations(FunctionalTestCase):
    """This test aims to exercise some generic caching operations in a semi-
    realistic scenario.
    
    The caching operations defined by GS profiles are grouped elsewhere.
    See `test_profile_without_caching_proxy.py` and `test_profile_with_caching_proxy.py`
    
    Note: Changes made using the API, accessing objects directly, are done
    with the Manager role set. Interactions are tested using the testbrowser.
    Unless explicitly logged in (e.g. by adding a HTTP Basic Authorization
    header), this accesses Plone as an anonymous user.
    
    The usual pattern is:
    
    * Configure caching settings
    * Set up test content
    * Create a new testbrowser
    * Set any request headers
    * Access content
    * Inspect response headers and body
    * Repeat as necessary
    
    To test purging, check the self.purger._sync and self.purger._async lists.
    """
    
    layer = Layer
    
    def afterSetUp(self):
        setRequest(self.portal.REQUEST)
        self.addProfile('plone.app.caching:without-caching-proxy')
        
        self.registry = getUtility(IRegistry)
        
        self.cacheSettings = self.registry.forInterface(ICacheSettings)
        self.cachePurgingSettings = self.registry.forInterface(ICachePurgingSettings)
        self.ploneCacheSettings = self.registry.forInterface(IPloneCacheSettings)
        
        self.purger = getUtility(IPurger)
        self.purger.reset()
    
    def beforeTearDown(self):
        setRequest(None)
    
    def test_disabled(self):
        self.cacheSettings.enabled = False
        
        self.setRoles(('Manager',))
        
        # Folder content
        self.portal.invokeFactory('Folder', 'f1')
        self.portal['f1'].setTitle(u"Folder one")
        self.portal['f1'].setDescription(u"Folder one description")
        self.portal['f1'].reindexObject()
        
        # Non-folder content
        self.portal['f1'].invokeFactory('Document', 'd1')
        self.portal['f1']['d1'].setTitle(u"Document one")
        self.portal['f1']['d1'].setDescription(u"Document one description")
        self.portal['f1']['d1'].setText("<p>Body one</p>")
        self.portal['f1']['d1'].reindexObject()
        
        # Content image
        self.portal['f1'].invokeFactory('Image', 'i1')
        self.portal['f1']['i1'].setTitle(u"Image one")
        self.portal['f1']['i1'].setDescription(u"Image one description")
        self.portal['f1']['i1'].setImage(OFS.Image.Image('test.gif', 'test.gif', open(TEST_IMAGE, 'rb')))
        self.portal['f1']['i1'].reindexObject()
        
        # Content file
        self.portal['f1'].invokeFactory('File', 'f1')
        self.portal['f1']['f1'].setTitle(u"File one")
        self.portal['f1']['f1'].setDescription(u"File one description")
        self.portal['f1']['f1'].setFile(OFS.Image.File('test.gif', 'test.gif', open(TEST_FILE, 'rb')))
        self.portal['f1']['f1'].reindexObject()
        
        # OFS image (custom folder)
        OFS.Image.manage_addImage(self.portal['portal_skins']['custom'], 'test.gif', open(TEST_IMAGE, 'rb'))
        
        # Resource registries resource
        cssResourcePath = self.portal['portal_css'].getEvaluatedResources(self.portal)[0].getId()
        
        self.setRoles(('Member',))
        
        browser = Browser()
        
        # Check that we can open all without errors and without cache headers
        browser.open(self.portal.absolute_url())
        self.failIf('Cache-Control' in browser.headers)
        
        browser.open(self.portal['f1'].absolute_url())
        self.failIf('Cache-Control' in browser.headers)
        
        browser.open(self.portal['f1']['d1'].absolute_url())
        self.failIf('Cache-Control' in browser.headers)
        
        browser.open(self.portal['f1']['i1'].absolute_url())
        self.failIf('Cache-Control' in browser.headers)
        
        browser.open(self.portal['f1']['f1'].absolute_url())
        self.failIf('Cache-Control' in browser.headers)
        
        browser.open(self.portal.absolute_url() + '/portal_skins/custom/test.gif')
        self.failIf('Cache-Control' in browser.headers)
        
        browser.open(self.portal.absolute_url() + '/++resource++plone.app.caching.gif')
        # Set by resources themselves, but irrelevant to this test:
        # self.failUnless('Cache-Control' in browser.headers)
        
        browser.open(self.portal.absolute_url() + '/portal_css/' + cssResourcePath)
        # Set by ResourceRegistries, btu irrelevant ot this test
        # self.failUnless('Cache-Control' in browser.headers)
    
    def test_gzip_setting(self):
        self.cacheSettings.enabled = True
        
        self.setRoles(('Manager',))
        
        # Folder content
        self.portal.invokeFactory('Folder', 'f1')
        self.portal['f1'].setTitle(u"Folder one")
        self.portal['f1'].setDescription(u"Folder one description")
        self.portal['f1'].reindexObject()
        
        # Non-folder content
        self.portal['f1'].invokeFactory('Document', 'd1')
        self.portal['f1']['d1'].setTitle(u"Document one")
        self.portal['f1']['d1'].setDescription(u"Document one description")
        self.portal['f1']['d1'].setText("<p>Body one</p>")
        self.portal['f1']['d1'].reindexObject()
        
        # GZip disabled, not accepted
        browser = Browser()
        self.ploneCacheSettings.enableCompression = False
        browser.open(self.portal['f1']['d1'].absolute_url())
        self.failIf('Vary' in browser.headers)
        self.failIf('gzip' in browser.headers.get('Content-Encoding', ''))
        
        # GZip disabled, accepted
        browser = Browser()
        browser.addHeader('Accept-Encoding', 'gzip')
        self.ploneCacheSettings.enableCompression = False
        browser.open(self.portal['f1']['d1'].absolute_url())
        self.failIf('Vary' in browser.headers)
        self.failIf('gzip' in browser.headers.get('Content-Encoding', ''))
        
        # GZip enabled, not accepted
        browser = Browser()
        self.ploneCacheSettings.enableCompression = True
        browser.open(self.portal['f1']['d1'].absolute_url())
        self.failIf('Vary' in browser.headers)
        self.failIf('gzip' in browser.headers.get('Content-Encoding', ''))
        
        # GZip enabled, accepted
        browser = Browser()
        self.ploneCacheSettings.enableCompression = True
        browser.addHeader('Accept-Encoding', 'gzip')
        browser.open(self.portal['f1']['d1'].absolute_url())
        self.failUnless('Accept-Encoding' in browser.headers['Vary'])
        self.assertEquals('gzip', browser.headers['Content-Encoding'])
        
        # Test as logged in (should not make any difference)
        browser = Browser()
        self.ploneCacheSettings.enableCompression = True
        
        browser.addHeader('Accept-Encoding', 'gzip')
        browser.addHeader('Authorization', 'Basic %s:%s' % (default_user, default_password,))
        
        browser.open(self.portal['f1']['d1'].absolute_url())
        self.failUnless('Accept-Encoding' in browser.headers['Vary'])
        self.assertEquals('gzip', browser.headers['Content-Encoding'])
    
    def test_auto_purge_content_types(self):
        
        self.setRoles(('Manager',))
        
        # Non-folder content
        self.portal.invokeFactory('Document', 'd1')
        self.portal['d1'].setTitle(u"Document one")
        self.portal['d1'].setDescription(u"Document one description")
        self.portal['d1'].setText("<p>Body one</p>")
        self.portal['d1'].reindexObject()
        
        self.setRoles(('Member',))
        
        # Purging disabled
        self.cachePurgingSettings.enabled = False
        self.cachePurgingSettings.cachingProxies = ()
        self.ploneCacheSettings.purgedContentTypes = ()
        
        editURL = self.portal['d1'].absolute_url() + '/edit'
        
        browser = Browser()
        browser.handleErrors = False
        
        browser.open(self.portal.absolute_url() + '/login')
        browser.getControl(name='__ac_name').value = default_user
        browser.getControl(name='__ac_password').value = default_password
        browser.getControl('Log in').click()
        
        browser.open(editURL)
        browser.getControl(name='title').value = u"Title 1"
        browser.getControl(name='form.button.save').click()
        
        self.assertEquals([], self.purger._sync)
        self.assertEquals([], self.purger._async)
        
        # Enable purging, but not the content type
        self.cachePurgingSettings.enabled = True
        self.cachePurgingSettings.cachingProxies = ('http://localhost:1234',)
        self.ploneCacheSettings.purgedContentTypes = ()
        
        browser.open(editURL)
        browser.getControl(name='title').value = u"Title 2"
        browser.getControl(name='form.button.save').click()
        
        self.assertEquals([], self.purger._sync)
        self.assertEquals([], self.purger._async)
        
        # Enable the content type, but disable purging
        self.cachePurgingSettings.enabled = False
        self.cachePurgingSettings.cachingProxies = ('http://localhost:1234',)
        self.ploneCacheSettings.purgedContentTypes = ()
        
        browser.open(editURL)
        browser.getControl(name='title').value = u"Title 3"
        browser.getControl(name='form.button.save').click()
        
        self.assertEquals([], self.purger._sync)
        self.assertEquals([], self.purger._async)
        
        # Enable properly
        self.cachePurgingSettings.enabled = True
        self.cachePurgingSettings.cachingProxies = ('http://localhost:1234',)
        self.ploneCacheSettings.purgedContentTypes = ('Document',)
        
        browser.open(editURL)
        browser.getControl(name='title').value = u"Title 4"
        browser.getControl(name='form.button.save').click()
        
        self.assertEquals([], self.purger._sync)
        self.assertEquals(set([
                'http://localhost:1234/plone/d1',
                'http://localhost:1234/plone/d1/document_view',
                'http://localhost:1234/plone/d1/',
                'http://localhost:1234/plone/d1/view']), set(self.purger._async))

def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)

