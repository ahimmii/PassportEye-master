from django import forms


class UploadForm(forms.Form):
    image = forms.FileField()
    legacy = forms.BooleanField(required=False)


