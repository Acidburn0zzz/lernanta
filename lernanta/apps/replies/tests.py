from django.test import Client
from django.contrib.auth.models import User

from replies.models import PageComment
from users.models import create_profile
from projects.models import Project, Participation
from content.models import Page

from test_utils import TestCase


class RepliesViewsTests(TestCase):

    test_username = 'testuser'
    test_email = 'test@p2pu.org'
    test_password = 'testpass'

    def setUp(self):
        self.client = Client()
        self.locale = 'en'
        django_user = User(
            username=self.test_username,
            email=self.test_email,
        )
        self.user = create_profile(django_user)
        self.user.set_password(self.test_password)
        self.user.save()

        self.project = Project(name='Reply Project',
            short_description='This project is to test replies',
            long_description='No really, its good',
        )
        self.project.save()
        
        participation = Participation(project=self.project,
            user=self.user, organizing=True)
        participation.save()
        
        self.page = Page(author=self.user,
            project=self.project,
            title='task title',
            sub_header='Tagline',
            content='Content',
            index=2)
        self.page.save()

    def test_comment(self):
        data = {
            'content': 'This is a comment',
        }
        self.client.login(username=self.test_username,
            password=self.test_password)
        comment_url = '/{0}/comments/create/page/content/{1}/project/projects/{2}/'.format(self.locale, self.page.id, self.project.id)
        response = self.client.post(comment_url, data)

        redirect_url = '/{0}/comments/1/'.format(self.locale)
        self.assertRedirects(response, redirect_url, target_status_code=302)
            
        comments = PageComment.objects.all()
        self.assertEquals(comments.count(), 1)

    def test_repy(self):

        comment = PageComment()
        comment.page_object = self.page
        comment.scope_object = self.project
        comment.author = self.user
        comment.content = "blah blah"
        comment.save()

        self.client.login(username=self.test_username, password=self.test_password)

        # post reply
        data = { 'content': 'This is a reply' }
        reply_url = '/{0}/comments/{1}/reply/'.format(self.locale, comment.id)
        response = self.client.post(reply_url, data)
            
        comments = PageComment.objects.all()
        self.assertEquals(comments.count(), 2)       

    def test_reply_by_email_hook(self):
        data = {
            u'from': [u'Dirk Uys <dirk@p2pu.org>'],
            u'attachments': [u'0'],
            u'to': [u'reply+abcdefghijklmnop@reply.p2pu.org'],
            u'text': [u'Maybe this time\n'],
            u'envelope': [u'{"to":["reply+abcdefghijklmnop@reply.p2pu.org"],"from":"dirk@p2pu.org"}'],
            u'headers': [
                u'Received: by 127.0.0.1 with SMTP id 7HNiGL0knF Thu, 21 Jun 2012 10:41:34 -0500 (CDT)\nReceived: from mail-ey0-f182.google.com (mail-ey0-f182.google.com [209.85.215.182]) by mx2.sendgrid.net (Postfix) with ESMTPS id 165E0179EA68 for <reply+abcdefghijklmnop@reply.p2pu.org>; Thu, 21 Jun 2012 10:41:33 -0500 (CDT)\nReceived: by eabm6 with SMTP id m6so287981eab.41 for <reply+abcdefghijklmnop@reply.p2pu.org>; Thu, 21 Jun 2012 08:41:31 -0700 (PDT)\nX-Google-DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed; d=google.com; s=20120113; h=mime-version:date:message-id:subject:from:to:content-type :x-gm-message-state; bh=U5LQcX1VeMMflboN7DWaD8mhHxEUMyxJKSioavl+PaY=; b=mod67Tg9pJkedv/ired6n89xAik5vPltmw+78esRAyAivlBnX845MVF1quPz3ApUCR 3D0a4knRfG1DXL7I5WHPUelHmT7vSurAtHPrW4ndJgyCoPjsd32rL9rIfrFpJGAWWd9+ DAO7gRMx0CtPNXL3UoOKtZTEMT1tF+Zt6UMPY+kZwP64lO4/k6dc6XYfGMYTEU2HUill CIftL/P7KjbcopBXpKF5YAJGHOazmw1QcRlTFaIW6ymW1uSZ5ieNUgZVQXIXw4/760O5 TJCZsh2qACfZ2PWWOfBV6bu0kjsab5TrsbBUdlu5uRoLeJxXqYzTroJ8+cbGPhrqZSGT 5XnA==\nMIME-Version: 1.0\nReceived: by 10.152.109.198 with SMTP id hu6mr26806411lab.21.1340293291509; Thu, 21 Jun 2012 08:41:31 -0700 (PDT)\nReceived: by 10.112.11.97 with HTTP; Thu, 21 Jun 2012 08:41:31 -0700 (PDT)\nDate: Thu, 21 Jun 2012 17:41:31 +0200\nMessage-ID: <CAAcFfF+a-WTypUHo2aPi_jjemNM8RRD3habXoFpopCOcFs=M0g@mail.gmail.com>\nSubject: test3\nFrom: Dirk Uys <dirk@p2pu.org>\nTo: reply+abcdefghijklmnop@reply.p2pu.org\nContent-Type: multipart/alternative; boundary=bcaec54b49d689096204c2fd5911\nX-Gm-Message-State: ALoCoQnzUWK4n+vh7QKSKjeJhgRrSUiCswAUpJmKNuhvGunMWMyixYjwSRwhiFRrOv0DHlpBmkke\n'],
            u'html': [u'Maybe this time<br>\n'],
            u'charsets': [u'{"to":"UTF-8","html":"ISO-8859-1","subject":"UTF-8","from":"UTF-8","text":"ISO-8859-1"}'],
            u'dkim': [u'none'],
            u'SPF': [u'none'],
            u'subject': [u'test3']
        }
        response = self.client.post('/%s/comments/email_reply/' % (self.locale,), data)
        self.assertEqual(response.status_code, 200)


    def test_reply_by_email(self):
        # post a comment
        comment = PageComment()
        comment.page_object = self.page
        comment.scope_object = self.project
        comment.author = self.user
        comment.content = "blah blah"
        comment.save()
        
        data = {
            u'from': [u'Testing <test@p2pu.org>'],
            u'to': [u'reply+{0}@reply.p2pu.org'.format(comment.reply_token)],
            u'text': [u'Maybe this time\n'],
            u'html': [u'Maybe this time<br>\n'],
            u'subject': [u'test3']
        }

        response = self.client.post('/%s/comments/email_reply/' % (self.locale,), data)
        self.assertEqual(response.status_code, 200)

        comments = PageComment.objects.all()
        self.assertEquals(comments.count(), 2)        
