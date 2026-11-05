from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password


class BootstrapFormMixin:
    """Aplica as classes do Bootstrap 5 a todos os campos do formulário."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                widget.attrs.setdefault("class", "form-check-input")
                continue
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class UsuarioForm(BootstrapFormMixin, forms.ModelForm):
    grupos = forms.ModelMultipleChoiceField(
        Group.objects.order_by("name"), required=False, widget=forms.CheckboxSelectMultiple,
        label="Perfis de acesso",
    )
    senha = forms.CharField(
        label="Senha", widget=forms.PasswordInput(render_value=False), required=False,
        help_text="Mínimo de 8 caracteres. Na edição, deixe em branco para manter a senha atual.",
    )
    senha_confirmacao = forms.CharField(label="Confirme a senha", widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        labels = {"username": "Usuário (login)", "first_name": "Nome", "last_name": "Sobrenome",
                  "is_active": "Usuário ativo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        if self.instance.pk:
            self.fields["grupos"].initial = self.instance.groups.all()
        else:
            self.fields["senha"].required = True
            self.fields["senha_confirmacao"].required = True

    def clean(self):
        dados = super().clean()
        senha, confirmacao = dados.get("senha"), dados.get("senha_confirmacao")
        if senha or confirmacao:
            if senha != confirmacao:
                self.add_error("senha_confirmacao", "As senhas não conferem.")
            else:
                try:
                    validate_password(senha, self.instance)
                except forms.ValidationError as erro:
                    self.add_error("senha", erro)
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get("senha"):
            usuario.set_password(self.cleaned_data["senha"])
        if commit:
            usuario.save()
            usuario.groups.set(self.cleaned_data["grupos"])
        return usuario
