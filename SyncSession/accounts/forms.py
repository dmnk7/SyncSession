from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


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


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Bitte Benutzername und Passwort prüfen. Beide Felder berücksichtigen die Groß-/Kleinschreibung.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Benutzername"
        self.fields["password"].label = "Passwort"
