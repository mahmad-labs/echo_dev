from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import APIToken, UserDevice, UserProfile, UserSession

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id','email','username','first_name','last_name','display_name','phone','country','timezone','language','is_verified','created_at')
        read_only_fields = ('id','is_verified','created_at')


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    class Meta:
        model = User
        fields = ('email','password','first_name','last_name','display_name','timezone','language')

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user); token['email'] = user.email; token['display_name'] = user.display_name
        return token


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value): raise serializers.ValidationError('Current password is incorrect.')
        return value
    def save(self):
        user=self.context['request'].user; user.set_password(self.validated_data['new_password']); user.save(update_fields=['password']); return user


class APITokenCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        from django.utils import timezone

        if value and value <= timezone.now():
            raise serializers.ValidationError('Expiration must be in the future.')
        return value


class APITokenSerializer(serializers.ModelSerializer):
    class Meta: model=APIToken; fields=('id','name','token_prefix','expires_at','last_used','revoked','created_at'); read_only_fields=fields

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta: model=UserProfile; exclude=('id',)
class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta: model=UserDevice; fields='__all__'; read_only_fields=('user',)
class UserSessionSerializer(serializers.ModelSerializer):
    class Meta: model=UserSession; fields='__all__'; read_only_fields=('user',)
