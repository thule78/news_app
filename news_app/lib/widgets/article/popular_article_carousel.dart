import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

import '../../models/article_model.dart';

class PopularArticleList extends StatelessWidget {
  const PopularArticleList({
    super.key,
    required this.items,
    required this.onTapArticle,
  });

  final List<ArticleModel> items;
  final void Function(ArticleModel article) onTapArticle;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (final article in items)
          Padding(
            padding: EdgeInsets.only(bottom: 12.h),
            child: InkWell(
              borderRadius: BorderRadius.circular(15.r),
              onTap: () => onTapArticle(article),
              child: Container(
                padding: EdgeInsets.all(10.w),
                decoration: BoxDecoration(
                  color: const Color(0xFFF7F6E5),
                  borderRadius: BorderRadius.circular(15.r),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 74.w,
                      height: 74.w,
                      decoration: BoxDecoration(
                        color: const Color(0xFFF7F6E5),
                        borderRadius: BorderRadius.circular(15.r),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(15.r),
                        child: article.image.isEmpty
                            ? const Icon(Icons.image_outlined)
                            : Image.network(
                                article.image,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) =>
                                    const Icon(Icons.broken_image_outlined),
                              ),
                      ),
                    ),
                    SizedBox(width: 12.w),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            article.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          SizedBox(height: 6.h),
                          Text(
                            article.description,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}
