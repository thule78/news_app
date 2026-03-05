import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../app_scope.dart';
import '../../core/utils/date_formatters.dart';
import '../../widgets/article/article_html_view.dart';
import '../../widgets/common/error_state.dart';
import '../../widgets/common/loading_indicator.dart';

class ArticleDetailScreen extends StatefulWidget {
  const ArticleDetailScreen({super.key, required this.articleId});

  final int articleId;

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      AppScope.of(context).articleDetailProvider.fetchDetail(widget.articleId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final detailProvider = AppScope.of(context).articleDetailProvider;
    final settingsProvider = AppScope.of(context).settingsProvider;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Article'),
        actions: [
          AnimatedBuilder(
            animation: detailProvider,
            builder: (context, child) => IconButton(
              onPressed: () => detailProvider.toggleLike(widget.articleId),
              icon: Icon(
                detailProvider.isLiked(widget.articleId)
                    ? Icons.favorite
                    : Icons.favorite_border,
              ),
            ),
          ),
          AnimatedBuilder(
            animation: detailProvider,
            builder: (context, child) => IconButton(
              onPressed: () => detailProvider.toggleBookmark(widget.articleId),
              icon: Icon(
                detailProvider.isBookmarked(widget.articleId)
                    ? Icons.bookmark
                    : Icons.bookmark_outline,
              ),
            ),
          ),
        ],
      ),
      body: AnimatedBuilder(
        animation: Listenable.merge([detailProvider, settingsProvider]),
        builder: (context, _) {
          if (detailProvider.isLoading) return const LoadingIndicator();
          if (detailProvider.error != null) {
            return ErrorState(
              message: detailProvider.error!,
              onRetry: () => detailProvider.fetchDetail(widget.articleId),
            );
          }

          final detail = detailProvider.detailFor(widget.articleId);
          if (detail == null) return const SizedBox.shrink();

          return SingleChildScrollView(
            padding: EdgeInsets.all(16.w),
            child: DefaultTextStyle(
              style: Theme.of(context).textTheme.bodyMedium!.copyWith(
                fontSize: 16.sp * settingsProvider.fontScale,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    detail.title,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  SizedBox(height: 8.h),
                  Text(
                    '${detail.author} • ${DateFormatters.shortDate(detail.publishedAt)}',
                  ),
                  SizedBox(height: 12.h),
                  if (detail.image.isNotEmpty)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12.r),
                      child: SizedBox(
                        width: double.infinity,
                        height: 210.h,
                        child: Image.network(
                          detail.image,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Container(
                            color: const Color(0xFFF7F6E5),
                            alignment: Alignment.center,
                            child: const Icon(Icons.broken_image_outlined),
                          ),
                        ),
                      ),
                    ),
                  SizedBox(height: 16.h),
                  Text(detail.description),
                  SizedBox(height: 16.h),
                  ArticleHtmlView(html: detail.contentHtml),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
