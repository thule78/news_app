class AuthRepository {
  String? _loggedInEmail;

  bool get isLoggedIn => _loggedInEmail != null && _loggedInEmail!.isNotEmpty;
  String get email => _loggedInEmail ?? '';

  Future<bool> login({required String email, required String password}) async {
    if (email.isEmpty || password.isEmpty) return false;
    _loggedInEmail = email.trim();
    return true;
  }

  Future<bool> signup({required String email, required String password}) async {
    return login(email: email, password: password);
  }

  void logout() {
    _loggedInEmail = null;
  }
}
