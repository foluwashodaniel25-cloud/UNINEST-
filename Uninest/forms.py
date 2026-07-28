from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import (
    User, StudentProfile, AgentProfile, LandlordProfile,
    StudentAgentProfile, Listing,
)


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("agent", "Agent"),
        ("landlord", "Landlord"),
        ("student_agent", "Student Agent"),
    ]
    full_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Full name"
    }))
    phone = forms.CharField(max_length=20, required=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Phone number"
    }))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        "class": "form-control", "placeholder": "Email address"
    }))
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, widget=forms.Select(attrs={
        "class": "form-select", "id": "role-select"
    }))

    class Meta:
        model = User
        fields = ("username", "email", "full_name", "phone", "role", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Password"})
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirm password"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data["phone"]
        user.role = self.cleaned_data["role"]
        name = self.cleaned_data["full_name"].strip().split(" ", 1)
        user.first_name = name[0]
        user.last_name = name[1] if len(name) > 1 else ""
        if commit:
            user.save()
        return user


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ("school_name", "department", "student_id_doc", "nin_doc")
        widgets = {
            "school_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "School name"}),
            "department": forms.TextInput(attrs={"class": "form-control", "placeholder": "Department"}),
            "student_id_doc": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "nin_doc": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("student_id_doc") and not cleaned.get("nin_doc"):
            raise forms.ValidationError("Upload either Student ID or NIN document.")
        return cleaned


class LandlordProfileForm(forms.ModelForm):
    location_of_house = forms.CharField(max_length=200, required=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Property location / area"
    }))
    number_of_rooms = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={
        "class": "form-control", "placeholder": "Number of rooms"
    }))
    price_per_room = forms.DecimalField(max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={
        "class": "form-control", "placeholder": "Price per room (₦)"
    }))
    full_address = forms.CharField(max_length=300, required=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Full house address"
    }))
    agent_details = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Agent details (optional)"
    }))
    photos = forms.FileField(required=False, widget=forms.FileInput(attrs={
        "class": "form-control", "accept": "image/*"
    }))

    class Meta:
        model = LandlordProfile
        fields = ("proof_of_ownership",)
        widgets = {
            "proof_of_ownership": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class StudentAgentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentAgentProfile
        fields = ("student_id_doc", "department", "course_rep_name")
        widgets = {
            "student_id_doc": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "department": forms.TextInput(attrs={"class": "form-control"}),
            "course_rep_name": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Course rep name"
            }),
        }


class ListingForm(forms.ModelForm):
    photos = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*"})
    )
    videos = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "video/*"})
    )

    class Meta:
        model = Listing
        fields = (
            "title", "general_location", "school_name", "description",
            "full_address", "landlord_name", "landlord_phone", "agent_phone",
            "rent_basis", "rent_amount", "agent_fee", "subsequent_rent",
            "max_tenants", "number_of_rooms",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "general_location": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Area / neighborhood"
            }),
            "school_name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "full_address": forms.TextInput(attrs={"class": "form-control"}),
            "landlord_name": forms.TextInput(attrs={"class": "form-control"}),
            "landlord_phone": forms.TextInput(attrs={"class": "form-control"}),
            "agent_phone": forms.TextInput(attrs={"class": "form-control"}),
            "rent_basis": forms.Select(attrs={"class": "form-select"}),
            "rent_amount": forms.NumberInput(attrs={"class": "form-control"}),
            "agent_fee": forms.NumberInput(attrs={"class": "form-control"}),
            "subsequent_rent": forms.NumberInput(attrs={"class": "form-control"}),
            "max_tenants": forms.NumberInput(attrs={"class": "form-control"}),
            "number_of_rooms": forms.NumberInput(attrs={"class": "form-control"}),
        }


class AgentVerificationForm(forms.Form):
    number_of_houses = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    landlord_details = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )
    nin_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Username or email"
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "form-control", "placeholder": "Password"
    }))


class SearchForm(forms.Form):
    school_name = forms.CharField(required=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "School name", "list": "schools"
    }))
    location = forms.CharField(required=True, widget=forms.TextInput(attrs={
        "class": "form-control", "placeholder": "Location / area"
    }))