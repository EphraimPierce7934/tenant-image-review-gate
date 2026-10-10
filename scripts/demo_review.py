from moderation_service.review_workflow import ReviewLabel, ReviewWorkflow


def main() -> None:
    workflow = ReviewWorkflow()
    tenant = workflow.onboard_tenant("Northwind Media")
    submission = workflow.submit_image(tenant.id, "campaign-cover.jpg", "img_demo_42")
    reviewed = workflow.review_image(
        submission.id,
        ReviewLabel.SAFE,
        "Brand-safe product image.",
    )
    print(f"{reviewed.filename}: {reviewed.state}")


if __name__ == "__main__":
    main()

