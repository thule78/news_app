class UserProfileModel {
  const UserProfileModel({
    required this.name,
    required this.email,
    required this.phone,
    required this.photoPath,
  });

  final String name;
  final String email;
  final String phone;
  final String photoPath;

  UserProfileModel copyWith({
    String? name,
    String? email,
    String? phone,
    String? photoPath,
  }) {
    return UserProfileModel(
      name: name ?? this.name,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      photoPath: photoPath ?? this.photoPath,
    );
  }

  static const empty = UserProfileModel(
    name: 'Guest User',
    email: '',
    phone: '',
    photoPath: '',
  );
}
