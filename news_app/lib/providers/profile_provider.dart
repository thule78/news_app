import 'package:flutter/material.dart';

import '../models/user_profile_model.dart';
import '../repositories/profile_repository.dart';

class ProfileProvider extends ChangeNotifier {
  ProfileProvider(this._profileRepository);

  final ProfileRepository _profileRepository;

  UserProfileModel get profile => _profileRepository.getProfile();

  void updateName(String name) {
    _profileRepository.updateName(name);
    notifyListeners();
  }

  void updatePhone(String phone) {
    _profileRepository.updatePhone(phone);
    notifyListeners();
  }

  void updatePhotoPath(String path) {
    _profileRepository.updatePhotoPath(path);
    notifyListeners();
  }

  String changePasswordLocalPlaceholder({
    required String oldPassword,
    required String newPassword,
  }) {
    if (oldPassword.isEmpty || newPassword.isEmpty) {
      return 'Please fill both password fields.';
    }
    return 'Password change saved locally (placeholder).';
  }
}
