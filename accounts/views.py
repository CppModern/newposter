from django.views.generic import CreateView
from .admin import UserCreationForm
from django.urls import reverse_lazy
from django.views import View
from .form import LoginForm
from django.http import (
    HttpRequest, HttpResponse,
)
from django.shortcuts import render
from .models import MyUser
from django.db import models


class SignupView(CreateView):

    template_name = "signup.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("account:thanks")


class Home(View):
    template_name = "account/login.html"
    form_class = LoginForm

    def get(self, request: HttpRequest):
        return render(
            request, self.template_name,
            context={"form": self.form_class()}
        )

    def post(self, request: HttpRequest):
        email = request.POST.get("email")
        password = request.POST.get("password")
        try:
            user: MyUser = MyUser.objects.get(email=email)
        except models.ObjectDoesNotExist:
            return render(
                request,
                self.template_name,
                context={
                        "form": self.form_class(),
                        "error": "Invalid login details"
                    }
                )
        if user.check_password(password):
            return HttpResponse("Welcome")
        return render(
            request,
            self.template_name,
            context={
                "form": self.form_class(),
                "error": "Invalid login details"
            }
        )

