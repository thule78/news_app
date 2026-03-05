import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../app_scope.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  static const List<String> _profilePhotoOptions = <String>[
    'lib/assets/images/catlover.jpeg',
    'lib/assets/images/doglover.jpg',
    'lib/assets/images/hedge.jpg',
  ];

  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _oldPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();
  String? _selectedPhotoPath;
  bool _didInitForm = false;

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _oldPasswordController.dispose();
    _newPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = AppScope.of(context).profileProvider;

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: AnimatedBuilder(
        animation: provider,
        builder: (context, _) {
          final profile = provider.profile;
          if (!_didInitForm) {
            _nameController.text = profile.name;
            _phoneController.text = profile.phone;
            _selectedPhotoPath = profile.photoPath.isEmpty
                ? _profilePhotoOptions.first
                : profile.photoPath;
            _didInitForm = true;
          }

          return ListView(
            padding: EdgeInsets.all(16.w),
            children: [
              Text(
                'Profile photo',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              SizedBox(height: 8.h),
              Wrap(
                spacing: 12.w,
                runSpacing: 12.h,
                children: _profilePhotoOptions.map((path) {
                  final isSelected = _selectedPhotoPath == path;
                  return GestureDetector(
                    onTap: () => setState(() => _selectedPhotoPath = path),
                    child: Container(
                      padding: EdgeInsets.all(3.w),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: isSelected
                              ? Theme.of(context).colorScheme.primary
                              : Colors.transparent,
                          width: 2.w,
                        ),
                      ),
                      child: CircleAvatar(
                        radius: 28.r,
                        backgroundImage: AssetImage(path),
                      ),
                    ),
                  );
                }).toList(growable: false),
              ),
              SizedBox(height: 16.h),
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              SizedBox(height: 12.h),
              TextField(
                controller: _phoneController,
                decoration: const InputDecoration(labelText: 'Phone'),
              ),
              SizedBox(height: 8.h),
              FilledButton(
                onPressed: () {
                  provider.updateName(_nameController.text.trim());
                  provider.updatePhone(_phoneController.text.trim());
                  if (_selectedPhotoPath != null) {
                    provider.updatePhotoPath(_selectedPhotoPath!);
                  }
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Profile updated')),
                  );
                },
                child: const Text('Save profile'),
              ),
              SizedBox(height: 20.h),
              const Text('Change password (local placeholder)'),
              SizedBox(height: 8.h),
              TextField(
                controller: _oldPasswordController,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Old password'),
              ),
              SizedBox(height: 12.h),
              TextField(
                controller: _newPasswordController,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'New password'),
              ),
              SizedBox(height: 8.h),
              OutlinedButton(
                onPressed: () {
                  final message = provider.changePasswordLocalPlaceholder(
                    oldPassword: _oldPasswordController.text,
                    newPassword: _newPasswordController.text,
                  );
                  ScaffoldMessenger.of(
                    context,
                  ).showSnackBar(SnackBar(content: Text(message)));
                },
                child: const Text('Update password'),
              ),
            ],
          );
        },
      ),
    );
  }
}
