"""
A base contact form for allowing users to send email messages through
a web interface.

"""
from django import forms
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.utils.translation import ugettext_lazy as _
from django.core.mail import send_mail
from django.template import loader


class ContactForm(forms.Form):
    """
    The base contact form class from which all contact form classes
    should inherit.

    """
    name = forms.CharField(max_length=100,
                           label=_(u'Your name'))
    last_name = forms.CharField(max_length=100,
                                label=_(u'Your last name'))
    phone_number = forms.CharField(max_length=100,
                                   label=_(u'Your phone number'))
    email = forms.EmailField(max_length=200,
                             label=_(u'Your email address'))
    title = forms.CharField(max_length=200,
                            label=_(u'Subject'))
    body = forms.CharField(widget=forms.Textarea,
                           label=_(u'Your message'))

    from_email = settings.DEFAULT_FROM_EMAIL

    recipient_list = [mail_tuple[1] for mail_tuple in settings.MANAGERS]

    subject_template_name = "contact_form/contact_form_subject.txt"

    template_name = 'contact_form/contact_form.txt'

    def __init__(self, data=None, files=None, request=None,
                 recipient_list=None, *args, **kwargs):
        if request is None:
            raise TypeError("Keyword argument 'request' must be supplied")
        self.request = request
        if recipient_list is not None:
            self.recipient_list = recipient_list
        super(ContactForm, self).__init__(data=data, files=files,
                                          *args, **kwargs)

    def from_email(self):
        """
        Use name and email for the "From:" header
        """
        return '"%s" <%s>' % (self.cleaned_data['name'],
                              self.cleaned_data['email'])

    def message(self):
        """
        Render the body of the message to a string.

        """
        template_name = self.template_name() if \
            callable(self.template_name) \
            else self.template_name
        return loader.render_to_string(
            template_name, self.get_context(), request=self.request
        )

    def subject(self):
        """
        Render the subject of the message to a string.

        """
        template_name = self.subject_template_name() if \
            callable(self.subject_template_name) \
            else self.subject_template_name
        subject = loader.render_to_string(
            template_name, self.get_context(), request=self.request
        )
        return ''.join(subject.splitlines())

    def get_context(self):
        """
        Return the context used to render the templates for the email
        subject and body.

        By default, this context includes:

        * All of the validated values in the form, as variables of the
          same names as their fields.

        * The current ``Site`` object, as the variable ``site``.

        * Any additional variables added by context processors (this
          will be a ``RequestContext``).

        """
        if not self.is_valid():
            raise ValueError(
                "Cannot generate Context from invalid contact form"
            )
        return dict(self.cleaned_data, site=get_current_site(self.request))

    def get_message_dict(self):
        """
        Generate the various parts of the message and return them in a
        dictionary, suitable for passing directly as keyword arguments
        to ``django.core.mail.send_mail()``.

        By default, the following values are returned:

        * ``from_email``

        * ``message``

        * ``recipient_list``

        * ``subject``

        """
        if not self.is_valid():
            raise ValueError(
                "Message cannot be sent from invalid contact form"
            )
        message_dict = {}
        for message_part in ('from_email', 'message',
                             'recipient_list', 'subject'):
            attr = getattr(self, message_part)
            message_dict[message_part] = attr() if callable(attr) else attr
        return message_dict

    def save(self, fail_silently=False):
        """
        Build and send the email message.

        """
        send_mail(fail_silently=fail_silently, **self.get_message_dict())


class AkismetContactForm(ContactForm):
    """
    Contact form which doesn't add any extra fields, but does add an
    Akismet spam check to the validation routine.

    Requires the Python Akismet library, and two configuration
    parameters: an Akismet API key and the URL the key is associated
    with. These can be supplied either as the settings AKISMET_API_KEY
    and AKISMET_BLOG_URL, or the environment variables
    PYTHON_AKISMET_API_KEY and PYTHON_AKISMET_BLOG_URL.

    """
    SPAM_MESSAGE = _(u"Your message was classified as spam.")

    def clean_body(self):
        if 'body' in self.cleaned_data:
            from akismet import Akismet
            akismet_api = Akismet(
                key=getattr(settings, 'AKISMET_API_KEY', None),
                blog_url=getattr(settings, 'AKISMET_BLOG_URL', None)
            )
            akismet_kwargs = {
                'user_ip': self.request.META['REMOTE_ADDR'],
                'user_agent': self.request.META.get('HTTP_USER_AGENT'),
                'comment_author': self.cleaned_data.get('name'),
                'comment_author_email': self.cleaned_data.get('email'),
                'comment_content': self.cleaned_data['body'],
                'comment_type': 'contact-form',
            }
            if akismet_api.comment_check(**akismet_kwargs):
                raise forms.ValidationError(
                    self.SPAM_MESSAGE
                )
            return self.cleaned_data['body']


class ReCaptchaContactForm(ContactForm):
    """
    Contact form which adds an extra field: captcha.

    Requires the Python django-recaptcha library, and two configuration
    parameters: a ReCaptcha public and private key. These can be
    supplied either as the settings RECAPTCHA_PUBLIC_KEY
    and RECAPTCHA_PRIVATE_KEY, or the environment variables
    PYTHON_RECAPTCHA_PUBLIC_KEY and PYTHON_RECAPTCHA_PRIVATE_KEY.

    Other options:
    - settings.RECAPTCHA_LANG: language code, string.
      See https://developers.google.com/recaptcha/docs/language
    """

    # Use reCAPTCHA v2
    setattr(settings, 'NOCAPTCHA', True)

    import os
    from captcha.fields import ReCaptchaField
    captcha = ReCaptchaField(
        attrs={'lang': getattr(settings, 'RECAPTCHA_LANG', None),
               'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
               'RECAPTCHA_PRIVATE_KEY': settings.RECAPTCHA_PRIVATE_KEY
               })
