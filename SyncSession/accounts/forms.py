from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("first_name", "last_name", "username")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Vorname"
        self.fields["first_name"].required = True
        self.fields["last_name"].label = "Nachname"
        self.fields["last_name"].required = True
        self.fields["username"].label = "Benutzername"
        self.fields["username"].help_text = "Damit meldest du dich an."
        self.fields["password1"].label = "Passwort"
        self.fields["password2"].label = "Passwort wiederholen"
        self.fields["password2"].help_text = ""
        self.order_fields(
            ["first_name", "last_name", "username", "password1", "password2"]
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Vorname"
        self.fields["first_name"].required = True
        self.fields["last_name"].label = "Nachname"
        self.fields["last_name"].required = True


class AccountDeleteForm(forms.Form):
    password = forms.CharField(
        label="Passwort",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Das Passwort ist nicht korrekt.")
        return password


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Bitte Benutzername und Passwort prüfen. Beide Felder berücksichtigen die Groß-/Kleinschreibung.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Benutzername"
        self.fields["password"].label = "Passwort"
