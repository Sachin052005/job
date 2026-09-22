from django import forms

from helpcenter.models import Feedback


class FeedbackForm(forms.ModelForm):
    rating = forms.ChoiceField(choices=[(i, str(i)) for i in range(1, 6)], widget=forms.RadioSelect)

    class Meta:
        model = Feedback
        fields = ["rating", "category", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


class ChatMessageForm(forms.Form):
    message = forms.CharField(
        max_length=1000, widget=forms.TextInput(attrs={"placeholder": "Ask your question..."})
    )
