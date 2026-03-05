import 'package:custom_refresh_indicator/custom_refresh_indicator.dart';
import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

class AppRefreshIndicator extends StatelessWidget {
  const AppRefreshIndicator({
    super.key,
    required this.child,
    required this.onRefresh,
  });

  final Widget child;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    return CustomRefreshIndicator(
      onRefresh: onRefresh,
      builder: (context, child, controller) {
        return AnimatedBuilder(
          animation: controller,
          builder: (context, _) {
            return Stack(
              alignment: Alignment.topCenter,
              children: [
                if (!controller.isIdle)
                  Positioned(
                    top: 12.h + (20.h * controller.value),
                    child: SizedBox(
                      height: 24.r,
                      width: 24.r,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.4,
                        value: controller.isLoading
                            ? null
                            : controller.value.clamp(0.0, 1.0),
                      ),
                    ),
                  ),
                Transform.translate(
                  offset: Offset(0, 56.h * controller.value),
                  child: child,
                ),
              ],
            );
          },
        );
      },
      child: child,
    );
  }
}
