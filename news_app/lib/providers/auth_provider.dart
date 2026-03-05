import 'package:flutter/material.dart';

import '../repositories/auth_repository.dart';
import '../repositories/profile_repository.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider(this._authRepository, this._profileRepository);

  final AuthRepository _authRepository;
  final ProfileRepository _profileRepository;

  bool _isSubmitting = false;
  String? _error;

  bool get isLoggedIn => _authRepository.isLoggedIn;
  bool get isSubmitting => _isSubmitting;
  String? get error => _error;
  String get email => _authRepository.email;

  Future<bool> login(String email, String password) async {
    _isSubmitting = true;
    _error = null;
    notifyListeners();

    final ok = await _authRepository.login(email: email, password: password);
    if (ok) {
      _profileRepository.setEmail(email);
    } else {
      _error = 'Email and password are required.';
    }

    _isSubmitting = false;
    notifyListeners();
    return ok;
  }

  Future<bool> signup(String email, String password) async {
    _isSubmitting = true;
    _error = null;
    notifyListeners();

    final ok = await _authRepository.signup(email: email, password: password);
    if (ok) {
      _profileRepository.setEmail(email);
    } else {
      _error = 'Email and password are required.';
    }

    _isSubmitting = false;
    notifyListeners();
    return ok;
  }

  void logout() {
    _authRepository.logout();
    notifyListeners();
  }
}
