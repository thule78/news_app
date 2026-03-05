import '../models/user_profile_model.dart';

class ProfileRepository {
  UserProfileModel _profile = UserProfileModel.empty;

  UserProfileModel getProfile() => _profile;

  void updatePhone(String phone) {
    _profile = _profile.copyWith(phone: phone);
  }

  void updateName(String name) {
    _profile = _profile.copyWith(name: name);
  }

  void updatePhotoPath(String photoPath) {
    _profile = _profile.copyWith(photoPath: photoPath);
  }

  void setEmail(String email) {
    _profile = _profile.copyWith(email: email);
  }
}
