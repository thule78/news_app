import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../app/theme/app_theme.dart';
import '../../../../router/route_names.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../user_data/presentation/providers/user_data_provider.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final currentUser = authProvider.currentUser;
    final userDataProvider = context.watch<UserDataProvider>();
    final profile = userDataProvider.profile;
    final displayName =
        profile?.displayName ?? currentUser?.resolvedName ?? 'Guest User';
    final email =
        profile?.email ?? currentUser?.resolvedEmail ?? 'guest@atmmovie.app';

    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        children: [
          Text('Profile', style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 20),
          const CircleAvatar(
            radius: 38,
            backgroundColor: AppTheme.softRed,
            child: Icon(
              Icons.person_rounded,
              color: AppTheme.primaryRed,
              size: 40,
            ),
          ),
          const SizedBox(height: 16),
          Text(displayName, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(email, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: 28),
          Card(
            child: Column(
              children: [
                _ProfileTile(
                  icon: Icons.edit_outlined,
                  title: 'Edit profile',
                  onTap: () => _showEditProfileDialog(context, displayName),
                ),
                const Divider(height: 1),
                const _ProfileTile(
                  icon: Icons.chat_bubble_outline_rounded,
                  title: 'My comments',
                ),
                const Divider(height: 1),
                const _ProfileTile(
                  icon: Icons.privacy_tip_outlined,
                  title: 'Privacy settings',
                ),
              ],
            ),
          ),
          if (userDataProvider.profileError != null) ...[
            const SizedBox(height: 16),
            Text(
              userDataProvider.profileError!,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
          const SizedBox(height: 24),
          OutlinedButton(
            onPressed: authProvider.isBusy
                ? null
                : () async {
                    await context.read<AuthProvider>().signOut();
                    if (!context.mounted) {
                      return;
                    }
                    Navigator.of(context).pushNamedAndRemoveUntil(
                      RouteNames.welcome,
                      (route) => false,
                    );
                  },
            child: Text(authProvider.isBusy ? 'Logging out...' : 'Log out'),
          ),
        ],
      ),
    );
  }

  Future<void> _showEditProfileDialog(
    BuildContext context,
    String initialName,
  ) async {
    final controller = TextEditingController(text: initialName);

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Edit profile'),
          content: TextField(
            controller: controller,
            decoration: const InputDecoration(labelText: 'Display name'),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () async {
                if (controller.text.trim().isEmpty) {
                  return;
                }
                await context.read<UserDataProvider>().updateProfileName(
                  controller.text.trim(),
                );
                if (!dialogContext.mounted) {
                  return;
                }
                Navigator.of(dialogContext).pop();
              },
              child: const Text('Save'),
            ),
          ],
        );
      },
    );
  }
}

class _ProfileTile extends StatelessWidget {
  const _ProfileTile({required this.icon, required this.title, this.onTap});

  final IconData icon;
  final String title;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: Icon(icon),
      title: Text(title),
      trailing: const Icon(Icons.chevron_right_rounded),
    );
  }
}
