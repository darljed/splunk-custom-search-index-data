# coding=UTF-8

#######################################################################
# IMPORTANT: Investigated this code and related files via SPL-194141.
# Despite being confident in being able to delete this code, since it
# has a non-zero chance of breaking a customer use case, we will err on
# the side of caution and add this comment instead of deleting.
#######################################################################

from splunk.appserver.mrsparkle.controllers import BaseController
from splunk.appserver.mrsparkle.lib.decorators import expose_page
from splunk.appserver.mrsparkle.lib.routes import route
import logging

logger = logging.getLogger('splunk.appserver.controllers.dashboardshare')

class DashboardShareController(BaseController):
    @route('/:action=new')
    @expose_page(must_login=True, methods='GET')
    def edit(self, action, **params):
        template_args = {}
        return self.render_template('dashboardshare/new.html', template_args)

    @route('/:action=create')
    @expose_page(must_login=True, methods='POST')
    def update(self, action, **params):
        template_args = {}
        success = True
        if success is False:
            return self.render_template('dashboardshare/new.html', template_args)
        return self.render_template('dashboardshare/success.html')
