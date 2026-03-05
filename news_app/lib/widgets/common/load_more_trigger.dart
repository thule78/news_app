import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

class LoadMoreTrigger extends StatelessWidget {
  const LoadMoreTrigger({
    super.key,
    required this.onPressed,
    required this.isLoading,
    this.label = 'Load more',
  });

  final VoidCallback onPressed;
  final bool isLoading;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: 12.h),
        child: isLoading
            ? const CircularProgressIndicator()
            : OutlinedButton(onPressed: onPressed, child: Text(label)),
      ),
    );
  }
}
