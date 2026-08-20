from django.core.mail import EmailMultiAlternatives

class SMTPMailer:
    def send(self,subject,text,to,*,html=None,reply_to=None):
        message=EmailMultiAlternatives(subject=subject,body=text,to=list(to),reply_to=list(reply_to or []))
        if html: message.attach_alternative(html,'text/html')
        return message.send(fail_silently=False)
